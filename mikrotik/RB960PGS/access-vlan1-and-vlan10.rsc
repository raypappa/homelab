# =============================================================================
# RB960PGS (hEX PoE) — L2 access, mixed VLAN 1 / VLAN 10 ports (desktop)
# =============================================================================
#
# Role: small 1G access switch at the desktop. Mix of VLAN 1 and VLAN 10
# access. Uplink SFP to the CCR2004 core. PoE-out on ether1..ether4 (configurable).
#
# Physical:
#   ether1..ether5 → 1G copper (PoE-out on 1-4 by default)
#   sfp             → trunk uplink to CCR2004
#
# Edit the variables at the top to match your cabling. Defaults: ether1-4 VLAN 1,
# ether5 VLAN 10 (for the third isolated device when it's at the desktop).
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName      "rb960pgs"
:local mgmtVlanId      1
:local vlan10Id        10
:local trunkToCore     "sfp"

# 1G copper ports as VLAN 1 (LAN) access
:local vlan1AccessPorts { "ether1"; "ether2"; "ether3"; "ether4" }

# 1G copper ports as VLAN 10 (isolated) access
:local vlan10AccessPorts { "ether5" }
# =============================================================================

# --- 1. Identity ------------------------------------------------------------
/system identity set name=$deviceName

# --- 2. Bridge with VLAN filtering ------------------------------------------
/interface bridge
:do {
  :if ([:len [/interface bridge find where name=bridge]] = 0) do={
    /interface bridge add name=bridge vlan-filtering=yes
  } else={
    /interface bridge set [find name=bridge] vlan-filtering=yes
  }
} on-error={ :put "bridge setup failed" }

# --- 3. VLAN entries --------------------------------------------------------
:do {
  /interface bridge vlan add bridge=bridge vlan-ids=$mgmtVlanId tagged=bridge,$trunkToCore \
      comment="mgmt-vlan"
} on-error={ :put "mgmt vlan entry exists" }
:do {
  /interface bridge vlan add bridge=bridge vlan-ids=$vlan10Id \
      tagged=bridge,$trunkToCore \
      comment="vlan10-trunk-and-bridge"
} on-error={ :put "vlan10 vlan entry exists" }

# --- 4. Trunk uplink --------------------------------------------------------
:do {
  /interface bridge port set [find interface=$trunkToCore] \
      pvid=$mgmtVlanId \
      frame-types=admit-all \
      comment="trunk-to-ccr2004"
} on-error={ :put "could not set trunk on uplink" }

# --- 5. VLAN 1 access ports -------------------------------------------------
:foreach port in=$vlan1AccessPorts do={
  :do {
    /interface bridge port set [find interface=$port] \
        pvid=$mgmtVlanId \
        frame-types=admit-only-untagged-and-priority-tagged \
        comment=("vlan1-access:" . $port)
  } on-error={ :put ("could not set vlan1 access on " . $port) }
}

# --- 6. VLAN 10 access ports ------------------------------------------------
:foreach port in=$vlan10AccessPorts do={
  :do {
    /interface bridge port set [find interface=$port] \
        pvid=$vlan10Id \
        frame-types=admit-only-untagged-and-priority-tagged \
        comment=("vlan10-access:" . $port)
  } on-error={ :put ("could not set vlan10 access on " . $port) }
}

# =============================================================================
# VERIFY AFTER IMPORT:
#   /interface bridge vlan print
#   /interface bridge port print
#   /interface bridge port print where pvid=10
# =============================================================================
