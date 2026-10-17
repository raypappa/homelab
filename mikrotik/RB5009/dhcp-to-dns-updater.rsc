# =============================================================================
# RB5009 — DHCP-to-DNS sync script (v4 A + v6 AAAA)
# =============================================================================
#
# Reads the bound DHCPv4 leases (and DHCPv6 leases, if /ipv6 dhcp-server is
# configured) and creates / updates / cleans DNS static records in
# /ip dns static. Records carry a comment of the form "dynamic_<servername>"
# so this script's records can be distinguished from hand-pinned static
# entries.
#
# Hooked into the DHCPv4 server via:
#   /ip dhcp-server set dhcp-vlan10 lease-script=DHCP-to-DNS-updater
# (and similarly for any other v4 servers in the $dhcpServers list).
#
# DHCPv6 hooks (RouterOS 7.10+):
#   /ipv6 dhcp-server set dhcpv6-vlan10 lease-script=DHCP-to-DNS-updater
#
# Domain: stoneydavis.internal (RFC 6762 reserved; not forwarded to public)
#
# Behavior:
#   - Reads each bound v4 lease; if host-name is set, creates an A record
#   - Reads each bound v6 lease; if host-name is set, creates an AAAA record
#   - Skips leases without a host-name (anonymous devices)
#   - Skips leases whose host-name matches the ignored list
#   - Cleans up DNS records whose lease no longer exists
#   - Idempotent: re-running on a clean state is a no-op
#
# To install: paste this file into /file on the device, then:
#   /system script add name=DHCP-to-DNS-updater source=[/file get DHCP-to-DNS-updater.rsc contents]
#   /file remove DHCP-to-DNS-updater.rsc
#   /ip dhcp-server set dhcp-vlan10 lease-script=DHCP-to-DNS-updater
#   /ipv6 dhcp-server set dhcpv6-vlan10 lease-script=DHCP-to-DNS-updater
# =============================================================================

:local dhcpServers { {"defconf"; "stoneydavis.internal"};
                      {"dhcp-vlan10"; "stoneydavis.internal"} };
:local dhcp6Servers { {"dhcpv6-vlan10"; "stoneydavis.internal"} };
:local ignoredHostNames { "localhost"; "LocalHost"; "localHost"; "Localhost" };
:local ttl "00:10:00";

# ----------------------------------------------------------------------------
# v4 leases -> A records
# ----------------------------------------------------------------------------
:foreach d in=$dhcpServers do={
  :local dhcpServerName ($d->0);
  :local dnsDomain      ($d->1);
  :local zoneExpr "";
  :if ( [ :len $dnsDomain ] > 0 ) do={ :set zoneExpr (".*." . $dnsDomain) }

  :local staticDNScomment ("dynamic_" . $dhcpServerName);

  # Cleanup: drop DNS records whose lease is gone
  :foreach i in=[/ip dns static find where name~("$zoneExpr") && comment=$staticDNScomment] do={
    :if ([/ip dns static get $i comment] = $staticDNScomment) do={
      :local hostname [/ip dns static get $i name];
      :if ( [ :len $dnsDomain ] > 0 ) do={
        :set hostname [ :pick $hostname 0 ([ :len $hostname ] - ([ :len $dnsDomain ] + 1)) ]
      }
      :local dhcpnode [/ip dhcp-server lease find where host-name=$hostname && server=$dhcpServerName && status=bound];
      :if ( [ :len $dhcpnode ] = 0 ) do={
        /ip dns static remove $i;
      }
    }
  }

  # Upsert: every bound lease gets an A record
  :foreach i in=[/ip dhcp-server lease find where server=$dhcpServerName && status=bound && dynamic=yes] do={
    :local hostname [/ip dhcp-server lease get $i host-name];
    :local dhcpip  [/ip dhcp-server lease get $i address];

    :local hostnameIsIgnored false;
    :if ( [ :len $hostname ] > 0 ) do={
      :foreach h in=$ignoredHostNames do={
        :if ($h = $hostname) do={ :set hostnameIsIgnored true }
      }
    }

    :if ( [ :len $hostname ] > 0 && $hostnameIsIgnored = false ) do={
      :if ( [ :len $dnsDomain ] > 0 ) do={ :set hostname ($hostname . "." . $dnsDomain) }
      :local dnsnode [/ip dns static find where name=$hostname && comment=$staticDNScomment];
      :if ( [ :len $dnsnode ] > 0 ) do={
        :local dnsip [/ip dns static get $dnsnode address];
        :if ( $dnsip != $dhcpip ) do={
          /ip dns static remove $dnsnode;
          /ip dns static add name=$hostname address=$dhcpip type=A \
              ttl=$ttl comment=$staticDNScomment;
        }
      } else={
        /ip dns static add name=$hostname address=$dhcpip type=A \
            ttl=$ttl comment=$staticDNScomment;
      }
    }
  }
}

# ----------------------------------------------------------------------------
# v6 leases -> AAAA records
# ----------------------------------------------------------------------------
:foreach d in=$dhcp6Servers do={
  :local dhcp6ServerName ($d->0);
  :local dnsDomain       ($d->1);
  :local zoneExpr "";
  :if ( [ :len $dnsDomain ] > 0 ) do={ :set zoneExpr (".*." . $dnsDomain) }

  :local staticDNScomment ("dynamic6_" . $dhcp6ServerName);

  # Cleanup: drop AAAA records whose lease is gone
  :foreach i in=[/ip dns static find where name~("$zoneExpr") && comment=$staticDNScomment && type=AAAA] do={
    :if ([/ip dns static get $i comment] = $staticDNScomment) do={
      :local hostname [/ip dns static get $i name];
      :if ( [ :len $dnsDomain ] > 0 ) do={
        :set hostname [ :pick $hostname 0 ([ :len $hostname ] - ([ :len $dnsDomain ] + 1)) ]
      }
      :local dhcp6node [/ipv6 dhcp-server lease find where host-name=$hostname && server=$dhcp6ServerName && status=bound];
      :if ( [ :len $dhcp6node ] = 0 ) do={
        /ip dns static remove $i;
      }
    }
  }

  # Upsert: every bound v6 lease gets an AAAA record
  :foreach i in=[/ipv6 dhcp-server lease find where server=$dhcp6ServerName && status=bound] do={
    :local hostname [/ipv6 dhcp-server lease get $i host-name];
    :local dhcp6ip [/ipv6 dhcp-server lease get $i address];

    :local hostnameIsIgnored false;
    :if ( [ :len $hostname ] > 0 ) do={
      :foreach h in=$ignoredHostNames do={
        :if ($h = $hostname) do={ :set hostnameIsIgnored true }
      }
    }

    :if ( [ :len $hostname ] > 0 && $hostnameIsIgnored = false ) do={
      :if ( [ :len $dnsDomain ] > 0 ) do={ :set hostname ($hostname . "." . $dnsDomain) }
      :local dnsnode [/ip dns static find where name=$hostname && comment=$staticDNScomment && type=AAAA];
      :if ( [ :len $dnsnode ] > 0 ) do={
        :local dnsip [/ip dns static get $dnsnode address];
        :if ( $dnsip != $dhcp6ip ) do={
          /ip dns static remove $dnsnode;
          /ip dns static add name=$hostname address=$dhcp6ip type=AAAA \
              ttl=$ttl comment=$staticDNScomment;
        }
      } else={
        /ip dns static add name=$hostname address=$dhcp6ip type=AAAA \
            ttl=$ttl comment=$staticDNScomment;
      }
    }
  }
}
