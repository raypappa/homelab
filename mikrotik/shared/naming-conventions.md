# Naming conventions

Every object on a MikroTik gets a name. These conventions make `print`
output self-documenting and let you grep for the role of a thing.

## Object names

| Pattern             | Example             | Used for                            |
| ------------------- | ------------------- | ----------------------------------- |
| `vlan10-svc`        | `vlan10-svc`        | SVI (interface vlan)                |
| `vlan10-pool`       | `vlan10-pool`       | DHCP address pool                   |
| `dhcp-vlan10`       | `dhcp-vlan10`       | DHCP server instance                |
| `bridge-core`       | `bridge-core`       | The device's L2 bridge              |
| `trunk-ccr2004`     | `trunk-ccr2004`     | Bridge port that trunks to the core |
| `port-iot-1`        | `port-iot-1`        | Access port (VLAN 10 / IoT)         |
| `port-lan-3`        | `port-lan-3`        | Access port (VLAN 1 / LAN)          |
| `capsman-mgr`       | `capsman-mgr`       | CAPsMAN manager config              |
| `cfg-5ghz-ac`       | `cfg-5ghz-ac`       | CAPsMAN configuration               |
| `security-wpa2-psk` | `security-wpa2-psk` | CAPsMAN security profile            |

## Comment conventions

Comments on objects include:

- **Role** ("trunk to CCR2004", "access VLAN 10")
- **Owner** (which config or script created it; helps with debugging)
- **Counterpart** (other end of a trunk or LAG)

Example:

```
/interface bridge port
add comment="trunk-to-ccr2004 - uplinked to sfp-sfpplus1" ...
```

## What not to do

- Don't use Mikrotik default names (`bridge`, `bridge1`, `ether1`) for new
  objects — keep them for the underlying physical/auto-created objects.
- Don't add `1`, `2` suffix in names that already contain a number
  (use `-01`, `-02` if you need a count for grep ordering).
