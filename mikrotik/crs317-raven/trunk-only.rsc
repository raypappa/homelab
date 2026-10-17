# =============================================================================
# CRS317-1G-16S+ — L2 fiber aggregation, trunk-only (raven)
# =============================================================================
#
# Role: 10G fiber aggregation point. All SFP+ ports are trunks upstream to
# the CCR2004 core. The 1G management port stays as VLAN 1 access for
# out-of-band mgmt if needed.
#
# Physical:
#   sfp-sfpplus1..16 → 10G SFP+ trunks (uplinks to other switches / devices)
#   ether1            → 1G copper (mgmt access, VLAN 1)
#
# No access ports on this device. If you need a device on a specific VLAN
# to plug in here, add its pvid to the variables block and add it to the
# vlan-ids tagging.
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local deviceName      "crs317"
:local mgmtVlanId      1
:local vlan10Id        10
:local mgmtPort        "ether1"

# 10G SFP+ ports that are trunks. By default all 16. Remove ones you don't use.
:local trunkPorts { "sfp-sfpplus1"; "sfp-sfpplus2"; "sfp-sfpplus3"; "sfp-sfpplus4"; \
                    "sfp-sfpplus5"; "sfp-sfpplus6"; "sfp-sfpplus7"; "sfp-sfpplus8"; \
                    "sfp-sfpplus9"; "sfp-sfpplus10"; "sfp-sfpplus11"; "sfp-sfpplus12"; \
                    "sfp-sfpplus13"; "sfp-sfpplus14"; "sfp-sfpplus15"; "sfp-sfpplus16" }
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
# VLAN 1: tagged on the bridge + the mgmt port (for OOB access)
:do {
  /interface bridge vlan add bridge=bridge vlan-ids=$mgmtVlanId tagged=bridge \
      comment="mgmt-vlan"
} on-error={ :put "mgmt vlan entry exists" }
# VLAN 10: tagged on the bridge + every trunk port
:do {
  :local trunkList ""
  :foreach p in=$trunkPorts do={
    :if ([:len $trunkList] > 0) do={ :set trunkList ($trunkList . ",") }
    :set trunkList ($trunkList . $p)
  }
  /interface bridge vlan add bridge=bridge vlan-ids=$vlan10Id \
      tagged=("bridge," . $trunkList) \
      comment="vlan10-trunk-ports"
} on-error={ :put "vlan10 vlan entry exists" }

# --- 4. Trunk ports (admit-all) ---------------------------------------------
:foreach port in=$trunkPorts do={
  :do {
    /interface bridge port set [find interface=$port] \
        pvid=$mgmtVlanId \
        frame-types=admit-all
  } on-error={ :put ("could not set trunk on " . $port) }
}

# --- 5. Mgmt port as VLAN 1 access -----------------------------------------
:do {
  /interface bridge port set [find interface=$mgmtPort] \
      pvid=$mgmtVlanId \
      frame-types=admit-only-untagged-and-priority-tagged \
      comment="mgmt-access-1g"
} on-error={ :put "could not set mgmt port pvid" }

# =============================================================================
# VERIFY AFTER IMPORT:
#   /interface bridge vlan print
#   /interface bridge port print
#   /interface bridge port print where frame-types=admit-all
# =============================================================================
