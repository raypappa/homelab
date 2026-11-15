# Internal DNS suffix migration

This repository migrates private service and host names from
`stoneydavis.internal` to `internal.stoneydavis.com`. The old suffix stays
available until the new records and clients are verified.

## Phase 1: publish both suffixes and issue the Argo certificate

### Before merging the DNS transition PR

1. Update the RouterOS `DHCP-to-DNS-updater` system-script source to the
   dual-publishing version in this repository, keeping its DHCPv4/v6 lease
   bindings intact. Run it once to backfill current leases, then verify both
   suffixes resolve. The existing `.rsc` file is script source: the Ansible
   import task does not install/update the RouterOS system-script object or its
   lease bindings. Also, the Mikrotik inventory group is currently commented
   out, so do not assume `task ansible:deploy -- -t mikrotik` will apply it.
1. Confirm the new host A/AAAA records resolve through RouterOS before merging;
   the NFS name and K3s control-plane names are among the consumers moving to
   the new suffix.

### After merging the transition PR

1. Let Argo CD reconcile the app DNS annotations and ExternalDNS filters. Both
   old and new service hostnames are intentionally requested.
1. Apply Headscale split-DNS changes through the normal Ansible path. For K3s,
   add the new SAN while retaining the old SAN; control-plane tasks restart K3s.
   Target control-plane hosts one at a time and schedule accordingly.
1. Let the cert-manager application reconcile `Certificate/argocd-server` in
   namespace `argocd`. It uses the existing
   `letsencrypt-stoneydavis-production` ClusterIssuer with DNS-01. Only ACME
   challenge TXT records go to the public Route 53 zone; internal A/AAAA
   records remain on MikroTik. Argo CD and the tunnel remain on their current
   HTTP-origin settings in this phase.

## Verify Phase 1 before enabling Argo TLS

From a client using the RouterOS resolver, check representative new and legacy
records (including an IPv6 lease):

```bash
dig A argocd.internal.stoneydavis.com @10.49.48.1
dig A argocd.stoneydavis.internal @10.49.48.1
dig AAAA <ipv6-host>.internal.stoneydavis.com @fd00:10::1
```

Also verify the NFS name from the cluster, both Headscale split-DNS zones, and
that the K3s API certificate contains both old and new SANs. The GitHub
`KUBE_CONFIG` secret is external to this repo; refresh it with the updated
README instructions when you intend scheduled Ansible runs to use the new API
hostname. Confirm the Argo Certificate is Ready and `argocd-server-tls` exists
in namespace `argocd`; do not print Secret data. The publicly trusted Argo
certificate will make its DNS name visible in Certificate Transparency logs.

## Phase 2: enable Argo HTTPS

Only after the Phase 1 Certificate is Ready, merge the separate Argo TLS change:
set `server.insecure` to false, expose Service port 443, and move the Cloudflare
Tunnel origin to HTTPS with `originServerName: argocd.internal.stoneydavis.com`.
The origin must validate normally; do not disable TLS verification.

Then verify `https://argocd.internal.stoneydavis.com` presents a trusted
certificate and `https://argocd.fieldsofbears.com` still works through the
Cloudflare tunnel. If either check fails, keep using the old DNS names and
revert the phase that failed. The old K3s SAN and DNS records remain available
for rollback.

## Phase 3: remove legacy records

After the new names have been stable and clients have moved, make a separate
cleanup change that removes `stoneydavis.internal` from the DHCP updater,
ExternalDNS filters/host annotations, Headscale split DNS, and K3s SANs. Remove
old script-managed RouterOS DNS records deliberately, checking their
`dynamic_*` / `dynamic6_*` comments before deletion. Then remove the temporary
legacy-domain variable and this transition guidance. Do not rely on ExternalDNS
or the DHCP updater to delete old records merely because the old suffix is no
longer configured.
