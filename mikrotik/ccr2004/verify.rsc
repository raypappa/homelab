# =============================================================================
# CCR2004 — verification commands (read-only)
# =============================================================================

# --- Identity / system -----------------------------------------------------
/system identity print
/interface print stats
/system resource print

# --- Bridge ----------------------------------------------------------------
/interface bridge print
/interface bridge vlan print
/interface bridge port print

# --- VLAN membership -------------------------------------------------------
/interface bridge vlan print where vlan-ids=10
/interface bridge port print where frame-types=admit-all
/interface bridge port print where pvid=10

# --- Useful for "did my tag get to the other end?" ------------------------
#   /tool sniffer quick filter="vlan 10"   # on the device connected to that trunk
