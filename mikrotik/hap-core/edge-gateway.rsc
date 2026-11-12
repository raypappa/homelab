# =============================================================================
# hAP be³ Media — edge gateway (replaces RB5009 WAN role)
# =============================================================================
#
# Role: 2.5G copper edge between the cable/DSL modem and the RB5009.
# Performs: WAN DHCP-client, staged VLAN 10 source NAT, VLAN 10 SVI with DHCP,
# and IPv4 VLAN 10 isolation. Existing RB5009 destination NAT rules are not
# copied here; add required port forwards and IPv6 isolation before migration.
#
# This is a substantial config. The order of operations is:
#   1. Apply the .rsc while it's still NOT the active gateway (i.e. RB5009
#      is still in the WAN path). The hAP's WAN port will have nothing
#      plugged in; VLAN 1 remains the management/upstream path to the RB5009.
#   2. When the time comes to flip: physically move the modem cable from
#      RB5009 ether1 to hAP ether1, then move the cable from RB5009
#      sfp-sfpplus1 to the RB5009 sfp-sfpplus1 (already there) — the
#      RB5009's trunk is set up for VLAN 1 + VLAN 10.
#   3. On the RB5009, remove the WAN-side masquerade + dst-nat rules
#      (now handled by the hAP) and remove the SVI for the WAN
#      (no longer used). DHCP for VLAN 10 also migrates here.
#   4. (Optional) move CAPsMAN off the RB5009 onto the hAP. The hAP has
#      RouterOS Level 6 license and the Wi-Fi 7 radios aren't being used
#      (cAP acs are your APs).
#
# Physical:
#   ether1 → WAN (cable/DSL modem, 1G)
#   ether2 → trunk uplink to RB5009 (sfp-sfpplus1 on RB5009, 1G or 2.5G)
#   ether3..ether5 → unused (left as VLAN 1 access by default)
#
# Pre-conditions:
#   - RB5009 already has VLAN 10 in place (see RB5009/vlan10-add.rsc)
#   - RB5009 sfp-sfpplus1 is configured as a trunk for VLAN 1 + VLAN 10
#
# Effect on existing traffic: the RB5009 stays the active gateway until you
# physically move the modem cable. Replacing the hAP bridge can briefly drop
# management connectivity; take a backup and ensure local recovery is possible.
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName       "router-on-stick"
:local mgmtVlanId       1
:local vlan10Id         10

:local wanPort          "ether1"
:local trunkToRB5009    "ether2"

:local vlan10Subnet     "10.10.10.0/24"
:local vlan10Gw         "10.10.10.1"
:local vlan10Address    "10.10.10.1/24"
:local vlan10Range      "10.10.10.10-10.10.10.254"
:local vlan10Lease      "1d"
:local lanSubnet        "10.49.48.0/23"
:local mgmtIp           "10.49.48.2/23"
:local mgmtGateway      "10.49.48.1"
# RB5009 is currently the active gateway.
:local dnsServers       "1.1.1.1,8.8.8.8"
:local vlan1AccessPorts { "ether3"; "ether4"; "ether5" }

# Static leases for the 3 isolated devices on VLAN 10
:local staticIot1       "44:B7:D0:E6:53:10"
:local staticIot1Ip     "10.10.10.20"
:local staticIot2       "FC:4C:EA:F9:71:0F"
:local staticIot2Ip     "10.10.10.21"
# The 3rd device MAC is still TBD — uncomment when known
# :local staticIot3       "AA:BB:CC:DD:EE:FF"
# :local staticIot3Ip     "10.10.10.22"
# =============================================================================

# --- 1. Identity ------------------------------------------------------------
/system identity set name=$deviceName
/ip dns set servers=$dnsServers allow-remote-requests=yes cache-size=4096KiB

# --- 2. Disable Wi-Fi (the cAP acs are the access points) --------------------
# cspell:ignore wifiwave
# RouterOS 7.13+ uses /interface wifi; older installs may use wifiwave2 or
# wireless. Catch unsupported menus so the wired gateway setup can continue.
:do {
  /interface wifi set [find] disabled=yes
} on-error={
  :do {
    /interface wifiwave2 set [find] disabled=yes
  } on-error={
    :do {
      /interface wireless set [find] disabled=yes
    } on-error={ :put "no supported Wi-Fi menu found; leaving radios unchanged" }
  }
}

# --- 3. Replace the factory bridge and prepare the VLAN-aware bridge --------
# Remove only the factory bridge. Preserve br-core on repeat imports.
:if ([:len [/interface bridge find where name="bridge"]] > 0) do={
  /interface bridge port remove [find where bridge="bridge"]
  /interface bridge remove [find where name="bridge"]
}

:if ([:len [/interface bridge find where name="br-core"]] = 0) do={
  /interface bridge add name=br-core vlan-filtering=no
} else={
  /interface bridge set [find where name="br-core"] vlan-filtering=no
}

# --- 4. Trunk port to RB5009 (tagged VLANs only) ----------------------------
:if ([:len [/interface bridge port find where interface=$trunkToRB5009]] = 0) do={
  /interface bridge port add bridge=br-core interface=$trunkToRB5009 \
      pvid=4094 frame-types=admit-only-vlan-tagged ingress-filtering=yes \
      comment="trunk-to-rb5009"
} else={
  /interface bridge port set [find where interface=$trunkToRB5009] \
      bridge=br-core pvid=4094 frame-types=admit-only-vlan-tagged \
      ingress-filtering=yes comment="trunk-to-rb5009"
}

# The copper access ports must be added after removing them from the factory
# bridge; setting a nonexistent bridge-port entry would silently do nothing.
:foreach port in=$vlan1AccessPorts do={
  :if ([:len [/interface bridge port find where interface=$port]] = 0) do={
    /interface bridge port add bridge=br-core interface=$port \
        pvid=$mgmtVlanId frame-types=admit-only-untagged-and-priority-tagged \
        ingress-filtering=yes comment=("vlan1-access:" . $port)
  } else={
    /interface bridge port set [find where interface=$port] \
        bridge=br-core pvid=$mgmtVlanId \
        frame-types=admit-only-untagged-and-priority-tagged \
        ingress-filtering=yes comment=("vlan1-access:" . $port)
  }
}

# --- 5. SVIs ---------------------------------------------------------------
:if ([:len [/interface vlan find where name="vlan1-mgmt"]] = 0) do={
  /interface vlan add name=vlan1-mgmt vlan-id=$mgmtVlanId interface=br-core
} else={
  /interface vlan set [find where name="vlan1-mgmt"] \
      vlan-id=$mgmtVlanId interface=br-core
}
:if ([:len [/interface vlan find where name="vlan10-isol"]] = 0) do={
  /interface vlan add name=vlan10-isol vlan-id=$vlan10Id interface=br-core
} else={
  /interface vlan set [find where name="vlan10-isol"] \
      vlan-id=$vlan10Id interface=br-core
}

# --- 6. Bridge VLAN membership ----------------------------------------------
# VLAN 1 is tagged to the RB5009 and bridge CPU, untagged on ether3-ether5.
# VLAN 10 is tagged to the RB5009 and bridge CPU. Install the table before
# enabling filtering so CPU and trunk membership are explicit.
:local vlan1AccessList ""
:foreach port in=$vlan1AccessPorts do={
  :if ([:len $vlan1AccessList] > 0) do={
    :set vlan1AccessList ($vlan1AccessList . ",")
  }
  :set vlan1AccessList ($vlan1AccessList . $port)
}

:if ([:len [/interface bridge vlan find where bridge="br-core" && vlan-ids=$mgmtVlanId]] = 0) do={
  /interface bridge vlan add bridge=br-core vlan-ids=$mgmtVlanId \
      tagged=("br-core," . $trunkToRB5009) untagged=$vlan1AccessList \
      comment="vlan1-management"
} else={
  /interface bridge vlan set [find where bridge="br-core" && vlan-ids=$mgmtVlanId] \
      tagged=("br-core," . $trunkToRB5009) untagged=$vlan1AccessList
}
:if ([:len [/interface bridge vlan find where bridge="br-core" && vlan-ids=$vlan10Id]] = 0) do={
  /interface bridge vlan add bridge=br-core vlan-ids=$vlan10Id \
      tagged=("br-core," . $trunkToRB5009) comment="vlan10-trunk"
} else={
  /interface bridge vlan set [find where bridge="br-core" && vlan-ids=$vlan10Id] \
      tagged=("br-core," . $trunkToRB5009)
}

/interface bridge set [find where name="br-core"] vlan-filtering=yes

# --- 7. IP addresses --------------------------------------------------------
:if ([:len [/ip address find where comment="hAP-edge-management"]] = 0) do={
  /ip address add address=$mgmtIp interface=vlan1-mgmt \
      comment="hAP-edge-management"
} else={
  /ip address set [find where comment="hAP-edge-management"] \
      address=$mgmtIp interface=vlan1-mgmt
}
:if ([:len [/ip address find where comment="hAP-edge-vlan10"]] = 0) do={
  /ip address add address=$vlan10Address interface=vlan10-isol \
      comment="hAP-edge-vlan10"
} else={
  /ip address set [find where comment="hAP-edge-vlan10"] \
      address=$vlan10Address interface=vlan10-isol
}

# --- 8. Default route via RB5009 (transient: until hAP becomes the gateway)
:if ([:len [/ip route find where comment="default via RB5009 (transient)"]] = 0) do={
  /ip route add dst-address=0.0.0.0/0 gateway=$mgmtGateway \
      comment="default via RB5009 (transient)"
} else={
  /ip route set [find where comment="default via RB5009 (transient)"] \
      dst-address=0.0.0.0/0 gateway=$mgmtGateway
}

# --- 9. DHCP for VLAN 10 ----------------------------------------------------
:if ([:len [/ip pool find where name="pool-vlan10"]] = 0) do={
  /ip pool add name=pool-vlan10 ranges=$vlan10Range
} else={
  /ip pool set [find where name="pool-vlan10"] ranges=$vlan10Range
}
:if ([:len [/ip dhcp-server find where name="dhcp-vlan10"]] = 0) do={
  /ip dhcp-server add name=dhcp-vlan10 interface=vlan10-isol \
      address-pool=pool-vlan10 lease-time=$vlan10Lease disabled=no \
      comment="vlan10-isolation-dhcp"
} else={
  /ip dhcp-server set [find where name="dhcp-vlan10"] \
      interface=vlan10-isol address-pool=pool-vlan10 \
      lease-time=$vlan10Lease disabled=no
}
:if ([:len [/ip dhcp-server network find where address=$vlan10Subnet]] = 0) do={
  /ip dhcp-server network add address=$vlan10Subnet \
      gateway=$vlan10Gw dns-server=$dnsServers
} else={
  /ip dhcp-server network set [find where address=$vlan10Subnet] \
      gateway=$vlan10Gw dns-server=$dnsServers
}

# --- 10. Static leases for isolated devices --------------------------------
:if ([:len [/ip dhcp-server lease find where comment="static-iot-1"]] = 0) do={
  /ip dhcp-server lease add address=$staticIot1Ip mac-address=$staticIot1 \
      server=dhcp-vlan10 comment="static-iot-1"
} else={
  /ip dhcp-server lease set [find where comment="static-iot-1"] \
      address=$staticIot1Ip mac-address=$staticIot1 server=dhcp-vlan10
}
:if ([:len [/ip dhcp-server lease find where comment="static-iot-2"]] = 0) do={
  /ip dhcp-server lease add address=$staticIot2Ip mac-address=$staticIot2 \
      server=dhcp-vlan10 comment="static-iot-2"
} else={
  /ip dhcp-server lease set [find where comment="static-iot-2"] \
      address=$staticIot2Ip mac-address=$staticIot2 server=dhcp-vlan10
}

# --- 11. WAN DHCP client (will only come up when the cable is moved) ---------
:if ([:len [/ip dhcp-client find where interface=$wanPort]] = 0) do={
  /ip dhcp-client add interface=$wanPort add-default-route=yes disabled=no \
      comment="wan-dhcp-client"
} else={
  /ip dhcp-client set [find where interface=$wanPort] \
      add-default-route=yes disabled=no comment="wan-dhcp-client"
}

# --- 12. Firewall: staged NAT and forwarding for VLAN 10 --------------------
# These rules only take effect once the hAP has its own WAN IP. They
# masquerade VLAN 10 traffic to the WAN interface. The rule is disabled
# initially so they don't fight RB5009's NAT while the hAP is in standby.
# When you flip the topology, enable both staged rules.
:if ([:len [/ip firewall nat find where comment="vlan10-internet-egress"]] = 0) do={
  /ip firewall nat add chain=srcnat src-address=$vlan10Subnet \
      out-interface=$wanPort action=masquerade disabled=yes \
      comment="vlan10-internet-egress"
} else={
  /ip firewall nat set [find where comment="vlan10-internet-egress"] \
      chain=srcnat src-address=$vlan10Subnet out-interface=$wanPort \
      action=masquerade disabled=yes
}
# Rebuild only these managed rules on every import so their order is stable.
/ip firewall filter remove [find where comment="allow-vlan10-wan"]
/ip firewall filter remove [find where comment="allow-vlan1-wan"]
/ip firewall filter remove [find where comment="isolate-vlan10-to-lan"]
/ip firewall filter remove [find where comment="isolate-lan-to-vlan10"]
/ip firewall filter remove [find where comment="drop-vlan10-to-router"]
/ip firewall filter remove [find where comment="allow-vlan10-dns-tcp"]
/ip firewall filter remove [find where comment="allow-vlan10-dns-udp"]
/ip firewall filter remove [find where comment="allow-vlan10-dhcp"]
/ip firewall filter remove [find where comment="allow-vlan1-management"]
/ip firewall filter remove [find where comment="drop-invalid-input"]
/ip firewall filter remove [find where comment="accept-established-input"]

# --- 13. Inter-VLAN isolation and WAN forwarding ----------------------------
# Add in final packet-processing order; place-before=0 keeps this managed block
# ahead of the router's existing broad accept/drop rules.
/ip firewall filter add chain=forward src-address=$vlan10Subnet \
    dst-address=$lanSubnet action=drop place-before=0 \
    comment="isolate-vlan10-to-lan"
/ip firewall filter add chain=forward src-address=$lanSubnet \
    dst-address=$vlan10Subnet action=drop place-before=0 \
    comment="isolate-lan-to-vlan10"
/ip firewall filter add chain=forward in-interface=vlan1-mgmt \
    out-interface=$wanPort action=accept place-before=0 \
    comment="allow-vlan1-wan"
/ip firewall filter add chain=forward in-interface=vlan10-isol \
    out-interface=$wanPort action=accept disabled=yes place-before=0 \
    comment="allow-vlan10-wan"

# --- 14. Router input policy -----------------------------------------------
# Permit established traffic, management from VLAN 1, and DHCP/DNS from VLAN
# 10; then block all other IPv4 access to the router from isolated devices.
/ip firewall filter add chain=input connection-state=established,related,untracked \
    action=accept place-before=0 comment="accept-established-input"
/ip firewall filter add chain=input connection-state=invalid action=drop \
    place-before=0 comment="drop-invalid-input"
/ip firewall filter add chain=input in-interface=vlan1-mgmt action=accept \
    place-before=0 comment="allow-vlan1-management"
/ip firewall filter add chain=input in-interface=vlan10-isol protocol=udp \
    dst-port=67 action=accept place-before=0 comment="allow-vlan10-dhcp"
/ip firewall filter add chain=input in-interface=vlan10-isol protocol=udp \
    dst-port=53 action=accept place-before=0 comment="allow-vlan10-dns-udp"
/ip firewall filter add chain=input in-interface=vlan10-isol protocol=tcp \
    dst-port=53 action=accept place-before=0 comment="allow-vlan10-dns-tcp"
/ip firewall filter add chain=input in-interface=vlan10-isol action=drop \
    place-before=0 comment="drop-vlan10-to-router"

# =============================================================================
# FLIP THE TOPOLOGY (when you're ready to make the hAP the active gateway):
#   1. On the hAP:  enable the rules tagged "vlan10-internet-egress" and
#      "allow-vlan10-wan". Add any required destination NAT port forwards.
#      Remove the transient default route via the RB5009:
#        /ip route remove [find comment="default via RB5009 (transient)"]
#   2. Physically:  move the modem cable from RB5009 ether1 to hAP ether1
#   3. On the RB5009:
#        /ip firewall nat remove [find comment="defconf: masquerade"]
#        /ip firewall nat remove [find comment~"puma|game wings|icarus|ark|matrix"]
#        /ip dhcp-server remove dhcp-vlan10
#        /ip firewall filter remove [find comment~"^isolate-"]
#      Keep the RB5009 IPv6 isolation rules until matching IPv6 routing and
#      firewall policy has been configured on the hAP.
#   4. Verify:  hAP's /ip address print shows 0.0.0.0/0 dynamic via dhcp-client
#
# VERIFY AFTER IMPORT (in standby state):
#   /ip address print
#   /interface bridge vlan print
#   /interface bridge port print
#   /ip dhcp-server lease print where server=dhcp-vlan10
#   /ip firewall filter print where chain=forward
#   /ip firewall filter print where chain=input
#   /ip firewall nat print
# =============================================================================
