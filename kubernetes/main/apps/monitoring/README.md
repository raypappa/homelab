# Infrastructure monitoring rollout

This directory adds opt-in exporters and read-only access to the existing Prometheus/Grafana stack. Exporters that need credentials or RouterOS preparation remain disabled until those prerequisites exist; no secret values or live changes belong in this repository.

## Exporters and target scope

- **MKTXP** (`akpw/mktxp`) covers the six MikroTik devices in `mikrotik/hosts.txt`. Its Argo app is disabled until API-SSL, a trusted RouterOS CA, and an out-of-band credential Secret are ready. The config disables user, DHCP-lease, connection, DNS, neighbor, public-IP, address-list, and update-check collectors to limit sensitive data and outbound calls.
- **Fishymetrics** (`Comcast/fishymetrics`) exposes its own `/metrics` endpoint now. The supplied iDRAC endpoint is `https://10.49.49.128`; the inactive `fishymetrics/service-monitor-idrac.disabled.yaml` stores the Redfish scrape definition but is deliberately not included by Kustomize. Enable it only after BMC credentials are supplied from a Secret and the target's TLS certificate behavior is validated; no skip-verify setting is configured. Fishymetrics accepts a bare IP in `target`; the deployment uses HTTPS. The supplied address is not yet confirmed as Puma's or storage-0001's iDRAC; the upstream documents `model` as optional, so it is omitted rather than guessed and the Prometheus instance label remains the IP. The target is in the existing `10.49.48.0/23` management subnet; no new router route is needed. Do not create a DHCP reservation unless the iDRAC MAC is known.
- **Cloudflare** uses `lablabs/cloudflare-exporter`: the user-provided `gitlab-org/cloudflare_exporter` repository is deprecated and explicitly directs users to this replacement. Its Argo app stays disabled until `cloudflare-exporter-credentials` exists with a `CF_API_TOKEN` key and `CF_ZONES` is set to the zone ID. Use a token scoped to the account containing `fieldsofbears.com`, with `Zone/Analytics:Read`; do not use a global API key. Pinned exporter v0.2.3 enumerates accounts and also requests Worker, Logpush, R2, load-balancer, and Zero Trust metrics; account-level scopes are required for some of those requests. Do not enable it until the account/zone IDs are confirmed and the token is limited to the intended account and metrics. The zone ID has not been supplied.

## Other supplied candidates

- **Ceph exporter:** deferred because the existing Rook/Ceph deployment already exposes Ceph metrics to Prometheus; another exporter would duplicate that path.
- **Disk-usage exporter:** deferred because node-exporter already supplies filesystem capacity/usage metrics. Revisit if directory-level accounting is specifically needed.
- **SNMP exporter:** deferred until there is an SNMP-only target. MKTXP is the direct RouterOS API exporter for the listed MikroTik devices.

## Sasha access

`monitoring-api-proxies` exposes only read/query endpoints for Prometheus and Grafana. `sasha-rbac` grants the `sasha` ServiceAccount read/list access to monitoring CRs and access to those two named Service proxy subresources; a namespaced Role permits reading only the `grafana-viewer-token` Secret in namespace `sasha`. The Grafana token itself is external to Git. Do not claim Grafana API access is ready until that Secret exists and contains a Viewer-scoped token.

The proxy paths are constrained in Nginx: Prometheus accepts read-only query/metadata/target endpoints; Grafana accepts read-only API endpoints plus `POST /api/ds/query` (a query operation under Viewer scope). All other paths/methods return 404/deny.

Call these through the Kubernetes API service-proxy path using the **bare Service name** (no `http:`/port suffix). Each Service has one port, and the bare name is what the namespaced RBAC rules authorize. For example, Prometheus uses `/api/v1/namespaces/monitoring/services/prometheus-query-proxy/proxy/api/v1/query`; Grafana uses `/api/v1/namespaces/monitoring/services/grafana-query-proxy/proxy/api/ds/query`. Grafana callers send `X-Grafana-Authorization: Bearer` with the token value read from the `grafana-viewer-token` Secret; never put the token in a URL. The Kubernetes ServiceAccount's API token authenticates the service-proxy request separately.

## Activation checklist

1. Provision each required credential via the existing external secret manager; never place values in Git or chat.
1. For MKTXP, apply the guarded RouterOS API-SSL template only after confirming the pod's actual source IP and installing a trusted certificate.
1. For Fishymetrics, add `BMC_USERNAME`/`BMC_PASSWORD` as Secret references to the Deployment, then include `service-monitor-idrac.disabled.yaml` in the app Kustomization.
1. For Cloudflare, create the scoped token Secret before enabling its Argo app.
1. Create the Grafana Viewer token Secret before using the Grafana API proxy.
1. Verify Argo reconciliation and Prometheus target health after deployment; rendered YAML alone does not prove live scrape success.
