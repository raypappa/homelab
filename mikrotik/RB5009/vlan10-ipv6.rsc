# =============================================================================
# RB5009 — VLAN 10 IPv6 (ULA + DHCPv6 + isolation FW)
# =============================================================================
#
# Additive on top of vlan10-add.rsc. Requires that the v4 SVI for VLAN 1
# and VLAN 10 already exist (named vlan1-svc and vlan10-svc respectively).
#
# What this does:
#   1. Adds ULA /64 addresses to the v4 SVIs (fd00:1::/64 and fd00:10::/64)
#   2. Enables IPv6 on the bridge and configures ND (RA) per VLAN
#   3. Stands up a DHCPv6 server per VLAN with the same subnet scheme
#   4. Pins static leases by DUID-EN (derived from MAC) for the 2 known
#      IoT devices on VLAN 10
#   5. Adds /ipv6 firewall filter rules matching the v4 isolation:
#      drop vlan10 <-> vlan1 in both directions
#   6. Local input chain: allow established/related, drop invalid, accept new
#
# Pre-conditions:
#   - vlan10-add.rsc has been imported; vlan1-svc and vlan10-svc exist
#   - The v4 SVI for VLAN 1 is the bridge (i.e. RB5009 is acting as L3)
#   - You're on RouterOS 7.10+ (DHCPv6 server is in there)
#
# Effect on existing traffic:
#   - IPv6 is added alongside IPv4; nothing IPv4 changes
#   - Devices that have IPv6 enabled will start picking up v6 addresses
#   - The v6 firewall drops block the same v4 inter-VLAN isolation
#
# To roll back: remove the v6 addrs, ND, DHCPv6 servers, and v6 filter
# rules (the script is intentionally additive; no /remove commands).
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName      "rb5009"

:local mgmtVlanId      1
:local vlan10Id        10

# ULA /64s (per VLAN). Use the same V4 naming on the SVI for clarity.
:local vlan1SviName    "vlan1-svc"             ; must match vlan10-add.rsc
:local vlan10SviName   "vlan10-svc"
:local vlan1V6Prefix   "fd00:1::/64"
:local vlan1V6Address  "fd00:1::1"
:local vlan10V6Prefix  "fd00:10::/64"
:local vlan10V6Address "fd00:10::1"

# DHCPv6 ranges (the first 16 are reserved for static; rest is dynamic)
:local vlan1V6Range    "fd00:1::10-fd00:1::ffff"
:local vlan10V6Range   "fd00:10::10-fd00:10::ffff"
:local dnsServersV6    "2606:4700:4700::1111,2001:4860:4860::8888"

# Static leases on VLAN 10 (DUID-EN format = "00030001" + MAC)
# DUID-EN: 4 bytes (DUID type + hw type) + 6 bytes (MAC)
# Examples:
#   MAC 44:B7:D0:E6:53:10  -> DUID 0003000144b7d0e65310
:local staticIot1      "44:B7:D0:E6:53:10"
:local staticIot1Duid  "0003000144b7d0e65310"
:local staticIot1V6Ip   "fd00:10::20"
:local staticIot2      "FC:4C:EA:F9:71:0F"
:local staticIot2Duid  "00030001fc4ceaf9710f"
:local staticIot2V6Ip   "fd00:10::21"
# :local staticIot3      "AA:BB:CC:DD:EE:FF"     ; uncomment when known
# :local staticIot3Duid  "00030001aabbccddeeff"
# :local staticIot3V6Ip   "fd00:10::22"
# =============================================================================

# --- 0. Enable IPv6 globally (no-op if already on) -------------------------
/ipv6 settings set disable-ipv6=no forward=no

# --- 1. ULA addresses on the SVIs -------------------------------------------
:do {
  /ipv6 address add address=$vlan1V6Address interface=$vlan1SviName \
      advertise=yes comment="vlan1-ula"
} on-error={ :put "vlan1 ULA address exists" }
:do {
  /ipv6 address add address=$vlan10V6Address interface=$vlan10SviName \
      advertise=yes comment="vlan10-ula"
} on-error={ :put "vlan10 ULA address exists" }

# --- 2. ND (RA) on each VLAN -----------------------------------------------
# managed-address-protocol=yes: clients should use DHCPv6 (not SLAAC)
# other-configuration=yes: clients get DNS via RA (RDNSS)
:do {
  /ipv6 nd add interface=$vlan1SviName \
      managed-address-protocol=yes \
      other-configuration=yes \
      ra-lifetime=30m \
      ra-interval=3m20s \
      dns=$vlan1V6Address \
      comment="vlan1-ra"
} on-error={ :put "vlan1 ND exists" }
:do {
  /ipv6 nd add interface=$vlan10SviName \
      managed-address-protocol=yes \
      other-configuration=yes \
      ra-lifetime=30m \
      ra-interval=3m20s \
      dns=$vlan10V6Address \
      comment="vlan10-ra"
} on-error={ :put "vlan10 ND exists" }

# --- 3. DHCPv6 server on each VLAN -----------------------------------------
# RouterOS v7.10+ has /ipv6 dhcp-server
:if ([:len [/ipv6 pool find where name=pool-v6-vlan1]] = 0) do={
  /ipv6 pool add name=pool-v6-vlan1 prefix=$vlan1V6Range prefix-length=64
}
:if ([:len [/ipv6 dhcp-server find where name=dhcpv6-vlan1]] = 0) do={
  /ipv6 dhcp-server add name=dhcpv6-vlan1 \
      interface=$vlan1SviName \
      address-pool=pool-v6-vlan1 \
      lease-time=1d \
      dns-server=$dnsServersV6 \
      disabled=no \
      comment="vlan1-dhcpv6"
}

:if ([:len [/ipv6 pool find where name=pool-v6-vlan10]] = 0) do={
  /ipv6 pool add name=pool-v6-vlan10 prefix=$vlan10V6Range prefix-length=64
}
:if ([:len [/ipv6 dhcp-server find where name=dhcpv6-vlan10]] = 0) do={
  /ipv6 dhcp-server add name=dhcpv6-vlan10 \
      interface=$vlan10SviName \
      address-pool=pool-v6-vlan10 \
      lease-time=1d \
      dns-server=$dnsServersV6 \
      disabled=no \
      comment="vlan10-dhcpv6"
}

# --- 4. Static leases on VLAN 10 (DUID-pinned) -----------------------------
:do {
  /ipv6 dhcp-server lease add address=$staticIot1V6Ip \
      duid=$staticIot1Duid server=dhcpv6-vlan10 comment="static-iot-1"
} on-error={ :put "static-iot-1 v6 lease exists" }
:do {
  /ipv6 dhcp-server lease add address=$staticIot2V6Ip \
      duid=$staticIot2Duid server=dhcpv6-vlan10 comment="static-iot-2"
} on-error={ :put "static-iot-2 v6 lease exists" }
# :do {
#   /ipv6 dhcp-server lease add address=$staticIot3V6Ip \
#       duid=$staticIot3Duid server=dhcpv6-vlan10 comment="static-iot-3"
# } on-error={ :put "static-iot-3 v6 lease exists" }

# --- 5. v6 firewall: isolation (matches v4) --------------------------------
# Two forward drops, one each direction. Place ABOVE any accept rule
# in the v6 forward chain, just like the v4 ones.
:do {
  /ipv6 firewall filter add chain=forward \
      src-address=$vlan10V6Prefix dst-address=$vlan1V6Prefix \
      action=drop comment="isolate-vlan10-to-lan-v6"
} on-error={ :put "v6 vlan10->vlan1 drop exists" }
:do {
  /ipv6 firewall filter add chain=forward \
      src-address=$vlan1V6Prefix dst-address=$vlan10V6Prefix \
      action=drop comment="isolate-lan-to-vlan10-v6"
} on-error={ :put "v6 vlan1->vlan10 drop exists" }

# --- 6. v6 local input: allow established/related, drop invalid, accept new -
/ipv6 firewall filter
add chain=input connection-state=established,related action=accept
add chain=input connection-state=invalid action=drop
add chain=input action=accept comment="allow all v6 input"

# =============================================================================
# VERIFY AFTER IMPORT:
#   /ipv6 address print
#   /ipv6 nd print
#   /ipv6 dhcp-server print
#   /ipv6 dhcp-server lease print where server=dhcpv6-vlan10
#   /ipv6 firewall filter print where chain=forward
#   /ipv6 route print
#
# FROM A CLIENT ON VLAN 10:
#   ip -6 addr            # should show fd00:10::/64 address
#   ip -6 route           # default via fd00:10::1
#   dig AAAA hostname.stoneydavis.internal @fd00:10::1
# =============================================================================
