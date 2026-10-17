# =============================================================================
# CRS326-24G-2S+ — L2 access, mixed VLAN 1 / VLAN 10 ports (rack 2)
# =============================================================================
#
# Role: 1G access switch in rack 2. Mix of VLAN 1 (LAN) and VLAN 10
# (isolated) ports. Uplink SFP+ trunks to the CCR2004 core.
#
# Physical:
#   ether1..24  → 1G copper access ports
#   sfp-sfpplus1 → trunk to CCR2004 (uplink)
#   sfp-sfpplus2 → unused (or second trunk to CCR2004 for LAG, later)
#
# Variables at the top: which ports are VLAN 1 access, which are VLAN 10
# access, and which SFP+ port is the trunk. Defaults are sensible; edit
# to match your actual cabling before importing.
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName      "crs326"
:local mgmtVlanId      1
:local vlan10Id        10
:local trunkToCore     "sfp-sfpplus1"

# 1G copper ports used as VLAN 1 (LAN) access, untagged
:local vlan1AccessPorts { "ether1"; "ether2"; "ether3"; "ether4"; "ether5"; "ether6"; "ether7"; "ether8"; "ether9"; "ether10"; "ether11"; "ether12"; "ether13"; "ether14"; "ether15"; "ether16"; "ether17"; "ether18"; "ether19"; "ether20"; "ether21"; "ether22" }

# 1G copper ports used as VLAN 10 (isolated) access, untagged
:local vlan10AccessPorts { "ether23"; "ether24" }
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

# --- 4. Trunk uplink to core (admit-all) -----------------------------------
:do {
  /interface bridge port set [find interface=$trunkToCore] \
      pvid=$mgmtVlanId \
      frame-types=admit-all \
      comment=("trunk-to-ccr2004")
} on-error={ :put "could not set trunk on uplink" }

# --- 5. VLAN 1 access ports (untagged) -------------------------------------
:foreach port in=$vlan1AccessPorts do={
  :do {
    /interface bridge port set [find interface=$port] \
        pvid=$mgmtVlanId \
        frame-types=admit-only-untagged-and-priority-tagged \
        comment=("vlan1-access:" . $port)
  } on-error={ :put ("could not set vlan1 access on " . $port) }
}

# --- 6. VLAN 10 access ports (untagged) ------------------------------------
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
