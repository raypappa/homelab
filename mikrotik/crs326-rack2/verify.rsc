# =============================================================================
# CRS326-24G-2S+ — verification commands (read-only)
# =============================================================================

# --- Identity --------------------------------------------------------------
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
/interface bridge port print where pvid=1

# --- Quick L2 sanity -------------------------------------------------------
#   /tool sniffer quick filter="vlan 10"   # on a device in VLAN 10
