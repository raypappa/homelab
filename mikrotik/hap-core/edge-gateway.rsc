# =============================================================================
# hAP be³ Media — edge gateway (replaces RB5009 WAN role)
# =============================================================================
#
# Role: 2.5G copper edge between the cable/DSL modem and the RB5009.
# Performs: WAN DHCP-client, NAT (srcnat + the dst-nat port forwards the
# RB5009 has today), VLAN 10 SVI with DHCP and isolation firewall.
#
# This is a substantial config. The order of operations is:
#   1. Apply the .rsc while it's still NOT the active gateway (i.e. RB5009
#      is still in the WAN path). The hAP's WAN port will have nothing
#      plugged in; SVI for VLAN 1 will exist but not be used.
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
# Effect on existing traffic: this script does NOT change the active
# gateway. RB5009 stays in the WAN path until you physically move the
# cable. Safe to apply.
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName       "hap-be3-media"
:local mgmtVlanId       1
:local vlan10Id         10

:local wanPort          "ether1"
:local trunkToRB5009    "ether2"

:local vlan10Subnet     "10.10.10.0/24"
:local vlan10Gw         "10.10.10.1"
:local vlan10Range      "10.10.10.10-10.10.10.254"
:local vlan10Lease      "1d"
:local lanSubnet        "10.49.48.0/23"
:local mgmtIp           "10.49.48.2/23"
:local mgmtGateway      "10.49.48.1"          ; RB5009 (currently the active gateway)
:local dnsServers       "1.1.1.1,8.8.8.8"

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

# --- 2. Wipe default config: factory has ether1=WAN, ethers 2-5 + WiFi = LAN
/interface bridge remove [find name=bridge]
/interface bridge port remove [find interface~$trunkToRB5009]

# --- 3. New bridge, VLAN-aware ---------------------------------------------
/interface bridge add name=br-core vlan-filtering=no
/interface bridge set br-core vlan-filtering=yes

# --- 4. Trunk port to RB5009 (admit-all = trunk) ---------------------------
/interface bridge port
add bridge=br-core interface=$trunkToRB5009 pvid=$mgmtVlanId frame-types=admit-all \
    comment="trunk-to-rb5009"

# --- 5. SVIs ---------------------------------------------------------------
/interface vlan
add name=vlan1-mgmt  vlan-id=$mgmtVlanId interface=br-core
add name=vlan10-isol vlan-id=$vlan10Id    interface=br-core

# --- 6. IP addresses -------------------------------------------------------
/ip address
add address=$mgmtIp    interface=vlan1-mgmt  comment="mgmt + upstream to RB5009"
add address=$vlan10Gw  interface=vlan10-isol comment="vlan10 gateway"

# --- 7. Default route via RB5009 (transient: until hAP becomes the gateway)
/ip route
add dst-address=0.0.0.0/0 gateway=$mgmtGateway comment="default via RB5009 (transient)"

# --- 8. DHCP for VLAN 10 ---------------------------------------------------
/ip pool add name=pool-vlan10 ranges=$vlan10Range
/ip dhcp-server add name=dhcp-vlan10 interface=vlan10-isol address-pool=pool-vlan10 \
    lease-time=$vlan10Lease disabled=no comment="vlan10-isolation-dhcp"
/ip dhcp-server network add address=$vlan10Subnet gateway=$vlan10Gw dns-server=$dnsServers

# --- 9. Static leases for isolated devices ---------------------------------
/ip dhcp-server lease
add address=$staticIot1Ip mac-address=$staticIot1 server=dhcp-vlan10 comment="static-iot-1"
add address=$staticIot2Ip mac-address=$staticIot2 server=dhcp-vlan10 comment="static-iot-2"

# --- 10. WAN DHCP client (will only come up when the cable is moved) ------
/ip dhcp-client add interface=$wanPort add-default-route=yes disabled=no \
    comment="wan-dhcp-client"

# --- 11. Firewall: NAT for VLAN 10 (only when hAP is the gateway) ---------
# These rules only take effect once the hAP has its own WAN IP. They
# masquerade VLAN 10 traffic to the WAN interface. The mask is `disabled=yes`
# initially so they don't fight RB5009's NAT while the hAP is in standby.
# When you flip the topology, set disabled=no.
:do {
  /ip firewall nat add chain=srcnat src-address=$vlan10Subnet \
      out-interface=$wanPort action=masquerade \
      comment="vlan10-internet-egress" disabled=yes
} on-error={ :put "vlan10 nat rule exists" }

# --- 12. Inter-VLAN isolation (v4) -----------------------------------------
# Drop VLAN 10 <-> VLAN 1 traffic both ways. Place these ABOVE any accept.
:do {
  /ip firewall filter add chain=forward \
      src-address=$vlan10Subnet dst-address=$lanSubnet action=drop \
      comment="isolate-vlan10-to-lan"
} on-error={ :put "vlan10->lan drop exists" }
:do {
  /ip firewall filter add chain=forward \
      src-address=$lanSubnet dst-address=$vlan10Subnet action=drop \
      comment="isolate-lan-to-vlan10"
} on-error={ :put "lan->vlan10 drop exists" }

# --- 13. Local input: allow established/related, drop invalid, accept new -
/ip firewall filter
add chain=input connection-state=established,related action=accept
add chain=input connection-state=invalid action=drop
add chain=input action=accept comment="allow all input"

# --- 14. Spare 3 copper ports as VLAN 1 access (ether3..ether5) -----------
:foreach port in={ "ether3"; "ether4"; "ether5" } do={
  :do {
    /interface bridge port set [find interface=$port] \
        pvid=$mgmtVlanId \
        frame-types=admit-only-untagged-and-priority-tagged \
        comment=("vlan1-access:" . $port)
  } on-error={ :put ("could not set vlan1 access on " . $port) }
}

# --- 15. Disable Wi-Fi (cAP acs are your APs) -----------------------------
/interface wireless set [find] disabled=yes

# =============================================================================
# FLIP THE TOPOLOGY (when you're ready to make the hAP the active gateway):
#   1. On the hAP:  /ip firewall nat enable [find comment="vlan10-internet-egress"]
#   2. Physically:  move the modem cable from RB5009 ether1 to hAP ether1
#   3. On the RB5009:
#        /ip firewall nat remove [find comment="defconf: masquerade"]
#        /ip firewall nat remove [find comment~"puma|game wings|icarus|ark|matrix"]
#        /ip dhcp-server remove dhcp-vlan10
#        /ip firewall filter remove [find comment~"^isolate-"]
#   4. Verify:  hAP's /ip address print shows 0.0.0.0/0 dynamic via dhcp-client
#
# VERIFY AFTER IMPORT (in standby state):
#   /ip address print
#   /interface bridge vlan print
#   /ip dhcp-server lease print where server=dhcp-vlan10
#   /ip firewall filter print where chain=forward
#   /ip firewall nat print
# =============================================================================
