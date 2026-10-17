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

| Variable          | Example                                     | Notes                                |
| ----------------- | ------------------------------------------- | ------------------------------------ |
| `vlan1SviName`    | `vlan1-svc`                                 | Must match the SVI name in v4 config |
| `vlan10SviName`   | `vlan10-svc`                                | Must match the SVI name in v4 config |
| `vlan1V6Prefix`   | `fd00:1::/64`                               | ULA /64 for VLAN 1                   |
| `vlan1V6Address`  | `fd00:1::1`                                 | Router's v6 on VLAN 1                |
| `vlan10V6Prefix`  | `fd00:10::/64`                              | ULA /64 for VLAN 10                  |
| `vlan10V6Address` | `fd00:10::1`                                | Router's v6 on VLAN 10               |
| `vlan1V6Range`    | `fd00:1::10-fd00:1::ffff`                   | DHCPv6 pool (first 16 reserved)      |
| `vlan10V6Range`   | `fd00:10::10-fd00:10::ffff`                 | DHCPv6 pool                          |
| `dnsServersV6`    | `2606:4700:4700::1111,2001:4860:4860::8888` | Cloudflare + Google v6               |

## DHCPv6 static leases (DUID-EN, derived from MAC)

DUID-EN format: `00030001` + MAC bytes (no colons, lowercase).

| Variable         | Example                | Notes                   |
| ---------------- | ---------------------- | ----------------------- |
| `staticIot1Duid` | `0003000144b7d0e65310` | MAC `44:B7:D0:E6:53:10` |
| `staticIot1V6Ip` | `fd00:10::20`          | Pinned v6 address       |
| `staticIot2Duid` | `00030001fc4ceaf9710f` | MAC `FC:4C:EA:F9:71:0F` |
| `staticIot2V6Ip` | `fd00:10::21`          | Pinned v6 address       |

## Physical

| Variable    | Example  | Notes                                 |
| ----------- | -------- | ------------------------------------- |
| `trunkPort` | `ether5` | Uplink to the device "above" this one |
| `wanPort`   | `ether1` | Edge device only                      |

## DNS / zone

| Variable  | Example                | Notes                             |
| --------- | ---------------------- | --------------------------------- |
| `dnsZone` | `stoneydavis.internal` | Internal-only zone (RFC 6762 TLD) |
