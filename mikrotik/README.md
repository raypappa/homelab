# Mikrotik configuration

RouterOS v7 `.rsc` scripts for the homelab fleet. Applied incrementally with
`/import file=foo.rsc` from each device's terminal.

## Topology

```
                Internet (1G)
                    │
              ┌─────▼─────┐
              │  hAP be³  │  edge (standby now; will replace RB5009 as WAN)
              │  Media    │
              └─────┬─────┘
                    │ 1G (or 2.5G; hAP has 5x 2.5G copper, no SFP)
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
└────────┘  └────────┘  └──────────┘
```

## VLANs

| VLAN | Subnet        | Purpose                                       |
| ---- | ------------- | --------------------------------------------- |
| 1    | 10.49.48.0/23 | Management / LAN (default)                    |
| 10   | 10.10.10.0/24 | Isolated subnet (3 devices, no LAN east-west) |

## Device roles

| Device            | Role        | Notes                                                                      |
| ----------------- | ----------- | -------------------------------------------------------------------------- |
| hAP be³ Media     | Edge        | Standby today (waiting to become WAN gateway). 2.5G copper only (no SFP).  |
| RB5009            | Gateway     | Currently WAN-facing. NAT, CAPsMAN, DHCP, VLAN 10 SVI, isolation firewall. |
| cAP ac (AP1, AP2) | Wi-Fi       | PoE from RB5009; AP2 daisy-chains off AP1.                                 |
| CCR2004           | Core        | L2 only; VLAN filtering on; all SFP+ (10G).                                |
| CRS326            | Access      | L2; rack 2; mix of VLAN 1 and VLAN 10 access ports.                        |
| RB960PGS          | Access      | L2; desktop; mix of VLAN 1 and VLAN 10 access ports.                       |
| CRS-317           | Aggregation | L2; fiber aggregation; trunk-only by default.                              |

## Order of operations

These are all safe to apply independently. They do not affect the active
gateway (RB5009) until you physically move the modem cable. Recommended
sequence:

1. **RB5009** — `vlan10-add.rsc` adds VLAN 10 (SVI, DHCP, isolation
   firewall) without touching existing NAT, port forwards, or CAPsMAN.
   **Safe to apply first.** Test the wired devices before proceeding.

1. **RB5009** — `vlan10-ipv6.rsc` adds ULA, DHCPv6, and v6 isolation
   firewall. Optional but recommended; skip if you don't want v6 yet.

1. **RB5009** — `dhcp-to-dns-updater.rsc` registers the script and
   hooks it to `dhcp-vlan10` and `dhcpv6-vlan10`. Creates A and AAAA
   records under `stoneydavis.internal` for every bound lease with a
   host-name. Skip if you don't want the DNS sync.

1. **CCR2004** — `core-trunk.rsc` enables VLAN filtering and configures
   trunk ports. Pure L2 changes; no risk to other devices.

1. **CRS326** + **RB960PGS** — `access-vlan1-and-vlan10.rsc` per device.
   L2 changes; safe.

1. **CRS-317** — `trunk-only.rsc`. L2; safe.

1. **hAP be³ Media** — `edge-gateway.rsc` is the last step because it
   wipes the factory default config (default bridge, default
   firewall, default Wi-Fi). The new device is fresh; the script
   deliberately removes the factory config and rebuilds. The script
   installs the device in **standby**: NAT rule is `disabled=yes`, WAN
   port has nothing plugged in, and the only active path is the
   10.49.48.0/23 SVI for management.

   The RB5009 continues to be the active gateway. When you want to
   flip the topology, follow the runbook at the bottom of
   `hAP-be3-media/edge-gateway.rsc`.

Each step is independently reversible: `/system backup load name=before-vlan-10`.

## Files

```
mikrotik/
├── README.md                  ← this file
├── shared/                    ← conventions + variable glossary
│   ├── naming-conventions.md
│   └── variables.md
├── RB5009/                    ← currently the active gateway
│   ├── vlan10-add.rsc         ← adds VLAN 10 SVI, DHCP, isolation FW (v4)
│   ├── vlan10-ipv6.rsc        ← adds ULA + DHCPv6 + v6 isolation FW
│   ├── dhcp-to-dns-updater.rsc← lease-sync script: v4 A + v6 AAAA records
│   ├── capsman.rsc            ← CAPsMAN controller config
│   └── verify.rsc
├── hAP-be3-media/             ← new edge, in standby
│   ├── edge-gateway.rsc       ← full L3 config; NAT disabled until flip
│   └── verify.rsc
├── CCR2004/                   ← L2 10G core
│   ├── core-trunk.rsc
│   └── verify.rsc
├── CRS326/                    ← 1G access (rack 2)
│   ├── access-vlan1-and-vlan10.rsc
│   └── verify.rsc
├── RB960PGS/                  ← 1G access (desktop)
│   ├── access-vlan1-and-vlan10.rsc
│   └── verify.rsc
└── CRS317/                    ← 10G fiber aggregation (raven)
    ├── trunk-only.rsc
    └── verify.rsc
```

## Conventions

- Each `.rsc` is **idempotent where possible**: re-running the script does
  not duplicate state. Where a step is one-shot (e.g. `set bridge vlan-filtering=yes`), the script documents the consequence at the top.
- Each script starts with a `# ============ VARIABLES ============` block.
  Edit values, not logic.
- Each device folder has a `verify.rsc` with `/print` commands to confirm
  state. Safe to paste into terminal — no side effects.
- Comments in `.rsc` use RouterOS `#` (no `;` line comments in v7).
