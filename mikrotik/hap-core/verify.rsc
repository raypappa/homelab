# =============================================================================
# hAP be³ Media — verification commands (read-only)
# =============================================================================

# --- Identity --------------------------------------------------------------
/system identity print
/interface print stats
/system resource print

# --- Bridge / VLAN --------------------------------------------------------
/interface bridge print
/interface bridge vlan print
/interface bridge port print

# --- IP / routing ---------------------------------------------------------
/ip address print
/ip route print
/ip dhcp-client print

# --- DHCP ----------------------------------------------------------------
/ip pool print
/ip dhcp-server print
/ip dhcp-server lease print where server=dhcp-vlan10
/ip dhcp-server lease print where server=dhcp-vlan10 status=bound

# --- Firewall -------------------------------------------------------------
/ip firewall nat print
/ip firewall filter print where chain=forward
/ip firewall filter print where comment~"^isolate-"

# --- Wireless (should be off) ---------------------------------------------
/interface wireless print
