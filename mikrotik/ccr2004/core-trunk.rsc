# =============================================================================
# CCR2004-1G-12S+2XS — L2 core, VLAN filtering
# =============================================================================
#
# Role: 10G L2 core in rack 1. Trunk to RB5009, fan-out to access switches.
# No SVIs, no DHCP, no NAT, no firewall. Pure L2.
#
# Physical (SFP+ ports 1-12, SFP28 ports 13-14):
#   sfp-sfpplus1  → trunk to RB5009
#   sfp-sfpplus2  → trunk to CRS326 (rack 2)
#   sfp-sfpplus3  → trunk to RB960PGS (desktop)
#   sfp-sfpplus4  → trunk to CRS-317 (raven)
#   sfp-sfpplus5..12, sfp28-1, sfp28-2 → unused (left as default L2 access)
#
# Pre-conditions:
#   - RB5009 already has VLAN 10 in place (see RB5009/vlan10-add.rsc)
#   - The RB5009 trunk port (sfp-sfpplus1 on RB5009) is configured for VLAN 1+10
#   - All trunks are 10G via direct-attach copper
#
# Effect:
#   - Enables VLAN filtering on the bridge
#   - VLAN 1 (mgmt) and VLAN 10 are tagged on all trunk ports
#   - Access ports (1G management port + unused SFP+) default to VLAN 1
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName       "ccr2004"
:local mgmtVlanId       1
:local vlan10Id         10
:local vlan10Subnet     "10.10.10.0/24"
:local lanSubnet        "10.49.48.0/23"

:local trunkToRB5009    "sfp-sfpplus1"
:local trunkToCRS326    "sfp-sfpplus2"
:local trunkToRB960PGS  "sfp-sfpplus3"
:local trunkToCRS317    "sfp-sfpplus4"

# SFP+ ports that are unused (left as VLAN 1 access, untagged)
:local unusedAccessPorts { }
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

# --- 3. VLAN entries on the bridge ------------------------------------------
# VLAN 1: all ports tagged so any device can be on mgmt if needed
# VLAN 10: all trunk ports tagged, no access ports on this device
:do {
  /interface bridge vlan add bridge=bridge vlan-ids=$mgmtVlanId tagged=bridge \
      comment="mgmt-vlan"
} on-error={ :put "mgmt vlan entry exists" }
:do {
  /interface bridge vlan add bridge=bridge vlan-ids=$vlan10Id \
      tagged=$trunkToRB5009,$trunkToCRS326,$trunkToRB960PGS,$trunkToCRS317 \
      comment="vlan10-trunk-ports"
} on-error={ :put "vlan10 vlan entry exists" }

# --- 4. Trunk ports (admit-all so 802.1Q tagged frames pass) ---------------
:foreach trunk in={ $trunkToRB5009; $trunkToCRS326; $trunkToRB960PGS; $trunkToCRS317 } do={
  :do {
    /interface bridge port set [find interface=$trunk] \
        pvid=$mgmtVlanId \
        frame-types=admit-all
  } on-error={ :put ("could not set trunk on " . $trunk) }
}

# --- 5. Spare SFP+ ports as VLAN 1 access (if user added any) ---------------
:foreach port in=$unusedAccessPorts do={
  :do {
    /interface bridge port set [find interface=$port] \
        pvid=$mgmtVlanId \
        frame-types=admit-only-untagged-and-priority-tagged
  } on-error={ :put ("could not set access pvid on " . $port) }
}

# =============================================================================
# VERIFY AFTER IMPORT:
#   /interface bridge vlan print
#   /interface bridge port print
#   /interface bridge print where name=bridge
#   /log print where topics~"bridge"
# =============================================================================
