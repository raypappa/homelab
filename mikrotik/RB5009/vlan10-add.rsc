# =============================================================================
# RB5009 — VLAN 10 isolation (additive, safe to import on top of existing)
# =============================================================================
#
# What this does:
#   1. Creates the vlan10 SVI on the existing LAN bridge
#   2. Adds a /24 address to that SVI
#   3. Stands up a DHCP server + pool for 10.10.10.0/24
#   4. Enables bridge VLAN filtering and tags the bridge port as VLAN 10 trunk
#   5. Converts two bridge ports (ether2, ether3) to VLAN 10 access
#   6. Adds a NAT rule for VLAN 10 to reach the internet
#   7. Drops inter-VLAN traffic (VLAN 10 <-> VLAN 1) at the forward chain
#
# Pre-conditions:
#   - Existing LAN is on 10.49.48.0/23 (your current setup)
#   - Existing NAT masquerade and dst-nat port forwards are untouched
#   - You have a `/system backup save name=before-vlan-10` snapshot
#
# Effect on existing traffic:
#   - Enabling `vlan-filtering=yes` on the bridge will briefly interrupt
#     L2 on the LAN while the change commits. In-flight TCP sessions reset.
#     Run in a maintenance window if you have anything sensitive up.
#   - Anything already plugged into ether2/ether3 that is NOT in VLAN 10
#     will lose connectivity. Move it to another port first.
#
# To roll back: /system backup load name=before-vlan-10
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName      "rb5009"
:local vlan10Id        10
:local vlan10Subnet    "10.10.10.0/24"
:local vlan10Gw        "10.10.10.1"
:local vlan10Range     "10.10.10.10-10.10.10.254"
:local vlan10Lease     "1d"
:local lanSubnet       "10.49.48.0/23"
:local dnsServers      "1.1.1.1,8.8.8.8"
:local vlan10AccessPorts { "ether2"; "ether3" }
# =============================================================================

# --- 1. SVI (interface vlan) -------------------------------------------------
:do {
  /interface vlan add name=("vlan" . $vlan10Id . "-svc") vlan-id=$vlan10Id interface=bridge \
      comment="vlan10-isolation-svi"
} on-error={ :put "vlan SVI already exists or add failed" }

# --- 2. IP address on the SVI -----------------------------------------------
:do {
  /ip address add address=($vlan10Gw . "/24") interface=("vlan" . $vlan10Id . "-svc") \
      comment="vlan10-gateway"
} on-error={ :put "vlan10 SVI address already set or add failed" }

# --- 3. DHCP pool + server + network ----------------------------------------
:if ([:len [/ip pool find where name="vlan10-pool"]] = 0) do={
  /ip pool add name=vlan10-pool ranges=$vlan10Range
}

:if ([:len [/ip dhcp-server find where name="dhcp-vlan10"]] = 0) do={
  /ip dhcp-server add name=dhcp-vlan10 \
      interface=("vlan" . $vlan10Id . "-svc") \
      address-pool=vlan10-pool \
      lease-time=$vlan10Lease \
      disabled=no \
      comment="vlan10-isolation-dhcp"
}

:if ([:len [/ip dhcp-server network find where address=$vlan10Subnet]] = 0) do={
  /ip dhcp-server network add address=$vlan10Subnet \
      gateway=$vlan10Gw \
      dns-server=$dnsServers
}

# --- 4. Bridge: enable VLAN filtering, tag the bridge port as VLAN 10 -------
/interface bridge set [find name=bridge] vlan-filtering=yes

:if ([:len [/interface bridge vlan find where bridge=bridge && vlan-ids=$vlan10Id]] = 0) do={
  /interface bridge vlan add bridge=bridge vlan-ids=$vlan10Id tagged=bridge \
      comment="vlan10-trunk-on-bridge"
}

# --- 5. Convert specified ports to VLAN 10 access ---------------------------
:foreach port in=$vlan10AccessPorts do={
  :do {
    /interface bridge port set [find interface=$port] \
        pvid=$vlan10Id \
        frame-types=admit-only-untagged-and-priority-tagged \
        comment=("vlan10-access:" . $port)
  } on-error={ :put ("could not set pvid on " . $port . " - check the port exists") }
}

# --- 6. NAT for VLAN 10 (outbound only) ------------------------------------
:if ([:len [/ip firewall nat find where src-address=$vlan10Subnet && action=masquerade]] = 0) do={
  /ip firewall nat add chain=srcnat \
      src-address=$vlan10Subnet \
      out-interface-list=WAN \
      action=masquerade \
      comment="vlan10-internet-egress"
}

# --- 7. Inter-VLAN isolation (DROPS — must sit above existing accept-all) ---
# Forward chain filters traffic passing THROUGH the router. The 10.49.48.0/23
# dst-address covers both directions because the rule uses src/dst prefixes
# and the drop is one-direction per rule. Two rules, one each way.
:do {
  /ip firewall filter add chain=forward \
      src-address=$vlan10Subnet \
      dst-address=$lanSubnet \
      action=drop \
      comment="isolate-vlan10-to-lan"
} on-error={ :put "vlan10->lan drop already exists" }

:do {
  /ip firewall filter add chain=forward \
      src-address=$lanSubnet \
      dst-address=$vlan10Subnet \
      action=drop \
      comment="isolate-lan-to-vlan10"
} on-error={ :put "lan->vlan10 drop already exists" }

# IMPORTANT: The two drops must sit ABOVE any accept rule on the forward
# chain that would otherwise let them through. After import, verify:
#   /ip firewall filter print where chain=forward
# If they are not at the top, drag them in WinBox (Firewall > Filter Rules
# > drag) or use:
#   /ip firewall filter move [find comment~"^isolate-"] [get [find where action=accept and chain=forward] numbers]

# =============================================================================
# VERIFY AFTER IMPORT:
#   /interface bridge vlan print where vlan-ids=10
#   /interface bridge port print where pvid=10
#   /ip dhcp-server lease print where server=dhcp-vlan10
#   /ip firewall filter print where comment~"^isolate-"
#   /ip address print where interface~"vlan10"
# =============================================================================
