# =============================================================================
# RB960PGS — verification commands (read-only)
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
/interface bridge port print where pvid=10
/interface bridge port print where pvid=1

# --- PoE (if you're powering APs/IoT from this switch) ---------------------
/interface ethernet print
/tool poe print
