# Variable glossary

Every `.rsc` starts with a `# ============ VARIABLES ============` block.
This file documents the variables that recur across the fleet.

## Identity

| Variable     | Example  | Notes                        |
| ------------ | -------- | ---------------------------- |
| `deviceName` | `rb5009` | `/system identity`           |
| `mgmtVlanId` | `1`      | Default for management / LAN |
| `vlan10Id`   | `10`     | Isolated subnet              |

## Addressing (RB5009 is the SVI owner for both VLANs)

| Variable       | Example         | Notes                            |
| -------------- | --------------- | -------------------------------- |
| `mgmtIp`       | `10.49.48.1/23` | SVI on `vlan1`                   |
| `vlan10Ip`     | `10.10.10.1/24` | SVI on `vlan10`                  |
| `lanSubnet`    | `10.49.48.0/23` | Used in firewall isolation rules |
| `vlan10Subnet` | `10.10.10.0/24` | Used in firewall isolation rules |
| `mgmtGateway`  | `10.49.48.1`    | Edge / upstream router (the hAP) |

## DHCP pools

| Variable      | Example                    | Notes                         |
| ------------- | -------------------------- | ----------------------------- |
| `vlan10Range` | `10.10.10.10-10.10.10.254` | Reserves `.2`–`.9` for static |
| `vlan10Lease` | `1d`                       | Bound DHCP lease time         |
| `dnsServers`  | `1.1.1.1,8.8.8.8`          | Forwarded by the RB5009       |

## IPv6 (ULAs only for now; switch to GUA if/when ISP does v6)

| Variable      | Example         | Notes                     |
| ------------- | --------------- | ------------------------- |
| `vlan1V6`     | `fd00:1::1/64`  | ULA /64 for VLAN 1        |
| `vlan10V6`    | `fd00:10::1/64` | ULA /64 for VLAN 10       |
| `vlan1V6Net`  | `fd00:1::/64`   | Used in v6 firewall rules |
| `vlan10V6Net` | `fd00:10::/64`  | Used in v6 firewall rules |

## Physical

| Variable    | Example  | Notes                                 |
| ----------- | -------- | ------------------------------------- |
| `trunkPort` | `ether5` | Uplink to the device "above" this one |
| `wanPort`   | `ether1` | Edge device only                      |

## DNS / zone

| Variable  | Example                | Notes                             |
| --------- | ---------------------- | --------------------------------- |
| `dnsZone` | `stoneydavis.internal` | Internal-only zone (RFC 6762 TLD) |
