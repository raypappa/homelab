# Mikrotik configuration

RouterOS v7 `.rsc` scripts for the homelab fleet. Applied incrementally with
`/import file=foo.rsc` from each device's terminal.

## Topology

```
                Internet (1G)
                    │
              ┌─────▼─────┐
              │  hAP be³  │  edge (2.5G WAN)
              │  Media    │
              └─────┬─────┘
                    │ 2.5G
              ┌─────▼─────┐
              │  RB5009   │  gateway / NAT / CAPsMAN / DHCP / firewall
              └─┬──────┬──┘
                │      │
         trunk  │      │  PoE  (AP2 daisy-chains off AP1)
                │      │
            ┌───▼─┐  ┌─▼────┐
            │ AP1 │  │ AP2  │  cAP ac (CAPsMAN-controlled)
            └─────┘  └──────┘
                │
                │ trunk
        ┌───────▼────────┐
        │   CCR2004      │  L2 core, 10G (rack 1)
        └─┬──────┬──────┬┘
          │      │      │
      10G │ 10G  │ 10G  │ 10G
   ┌──────┘      │      └──────┐
   │             │             │
┌──▼─────┐  ┌────▼─────┐  ┌────▼─────┐
│ CRS326 │  │ RB960PGS │  │ CRS-317  │
│ rack 2 │  │ desktop  │  │ raven    │
└────────┘  └──────────┘  └──────────┘
```

## VLANs

| VLAN | Subnet        | Purpose                                       |
| ---- | ------------- | --------------------------------------------- |
| 1    | 10.49.48.0/23 | Management / LAN (default)                    |
| 10   | 10.10.10.0/24 | Isolated subnet (3 devices, no LAN east-west) |

## Device roles

| Device            | Role        | Notes                                                  |
| ----------------- | ----------- | ------------------------------------------------------ |
| hAP be³ Media     | Edge        | New; WAN + trunk to RB5009. 2.5G copper only (no SFP). |
| RB5009            | Gateway     | NAT, CAPsMAN, DHCP, VLAN 10 SVI, isolation firewall.   |
| cAP ac (AP1, AP2) | Wi-Fi       | PoE from RB5009; AP2 daisy-chains off AP1.             |
| CCR2004           | Core        | L2 only; VLAN filtering on; all SFP+ (10G).            |
| CRS326            | Access      | L2; rack 2; mix of VLAN 1 and VLAN 10 access ports.    |
| RB960PGS          | Access      | L2; desktop; mix of VLAN 1 and VLAN 10 access ports.   |
| CRS-317           | Aggregation | L2; fiber aggregation; trunk-only by default.          |
| hAP be³ Media     | Edge        | 2.5G copper to RB5009 (1G internet is the bottleneck). |

## Order of operations

1. **RB5009** — `vlan10-add.rsc` adds VLAN 10 (SVI, DHCP, isolation firewall)
   without touching existing NAT, port forwards, or CAPsMAN. **Safe to apply
   first.** Test the two wired devices before proceeding.
1. **CCR2004** — `core-trunk.rsc` enables VLAN filtering and configures
   trunk ports. Verify VLAN 10 traverses end-to-end.
1. **CRS326 / RB960PGS** — `access-vlan1-and-vlan10.rsc` per device.
1. **CRS-317** — `trunk-only.rsc` (no SVI, no access ports).
1. **hAP be³ Media** — replaces the edge role; rebalance trunk
   uplink from RB5009 to hAP. This is the last step because it changes
   the gateway; the previous four are gateway-agnostic.

Each step is independently reversible: `/system backup load name=before-vlan-10`.

## Files

```
mikrotik/
├── README.md                  ← this file
├── shared/                    ← conventions + variable glossary
│   ├── naming-conventions.md
│   └── variables.md
└── RB5009/                    ← device folders; one per MikroTik
    ├── vlan10-add.rsc         ← imports on top of existing config
    ├── capsman.rsc            ← your CAPsMAN config (controller-side)
    └── verify.rsc             ← read-only print commands
```

## Conventions

- Each `.rsc` is **idempotent where possible**: re-running the script does
  not duplicate state. Where a step is one-shot (e.g. `set bridge vlan-filtering=yes`), the script documents the consequence at the top.
- Each script starts with a `# ============ VARIABLES ============` block.
  Edit values, not logic.
- Each device folder has a `verify.rsc` with `/print` commands to confirm
  state. Safe to paste into terminal — no side effects.
- Comments in `.rsc` use RouterOS `#` (no `;` line comments in v7).
