# =============================================================================
# RB5009 — verification commands (read-only)
# =============================================================================
# Paste any of these into the RB5009 terminal to inspect state.
# Nothing here changes the device.

# --- Identity / system -----------------------------------------------------
/system identity print
/system backup print

# --- VLAN 10 (SVI, address, DHCP) ------------------------------------------
/interface vlan print where vlan-id=10
/ip address print where interface~"vlan10"
/ip pool print where name=vlan10-pool
/ip dhcp-server print where name=dhcp-vlan10
/ip dhcp-server network print where address=10.10.10.0/24
/ip dhcp-server lease print where server=dhcp-vlan10

# --- Bridge VLAN filtering + ports -----------------------------------------
/interface bridge print where name=bridge
/interface bridge vlan print where vlan-ids=10
/interface bridge port print where pvid=10

# --- Firewall (NAT + isolation) --------------------------------------------
/ip firewall nat print
/ip firewall filter print where chain=forward
/ip firewall filter print where comment~"^isolate-"

# --- CAPsMAN ---------------------------------------------------------------
/caps-man manager print
/caps-man provisioning print
/caps-man registration-table print
/caps-man interface print

# --- DHCPv4 leases (all, with status) --------------------------------------
/ip dhcp-server lease print detail where dynamic=no
/ip dhcp-server lease print where status=bound

# --- Active connections / interfaces ---------------------------------------
/ip route print where !dynamic
/interface print stats
