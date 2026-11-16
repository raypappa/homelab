---
name: cloudflare-pulumi-tunnels
description: Use when adding or changing a remotely managed Cloudflare Tunnel. Keep its full ingress configuration in Pulumi and verify the planned import/update before applying it.
version: 0.1.0
author: Craig (raypappa), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [homelab, Cloudflare, Pulumi, tunnels, infrastructure]
    related_skills: []
---

# Cloudflare Tunnel Configuration with Pulumi

Manage Cloudflare dashboard/API-managed tunnels in `pulumi/stacks/cloudflare_tunnels.py`. This registry currently adopts `faerun-argocd`; add other UI-managed tunnels incrementally after reviewing their live configuration. Tunnels with `config_src: local` remain managed by their local `cloudflared` configuration and must not be added here.

## Prerequisites

- Work from the repository root and use the Pulumi project under `pulumi/`.
- Configure `cloudflare:accountId`, `cloudflare:argocdTunnelId`, and `cloudflare:apiToken` in the Pulumi stack. When using the Pulumi Cloud dashboard, place them under `values.pulumiConfig` in an ESC environment, mark `cloudflare:apiToken` with `fn::secret`, and link that environment to the stack.
- The token needs Account-level Cloudflare Tunnel Read and Write permissions and should be scoped to the account containing the tunnel. Do not reuse the cert-manager DNS token unless its scopes are verified.
- The v6.24.0 provider schema does not model Cloudflare API's top-level `warp-routing` field. The Argo tunnel's live value is disabled and recorded as `observed_unsupported_config`; do not enroll tunnels with WARP routing enabled until provider support exists, and stop if preview proposes an unexpected change there.
- The runtime must also have the existing Pulumi backend and AWS credentials available because Cloudflare shares the current Pulumi project with existing AWS resources.

## Adding a Tunnel

1. Read the complete live configuration for the target tunnel before editing. Preserve every ingress route, its order, per-ingress and top-level origin request settings, and the final `http_status:404` catch-all. Cloudflare's configuration update replaces the whole configuration; account for provider fields it does not model.
1. Add the tunnel's ID config key and complete provider-supported config object to `REMOTE_TUNNELS`, not just its ingress list. Do not add locally managed tunnels. Keep TLS verification enabled unless the tunnel explicitly has a separately reviewed reason not to.
1. Use `cloudflare.ZeroTrustTunnelCloudflaredConfig` with `source="cloudflare"` and an import ID of `<account_id>/<tunnel_id>` so Pulumi adopts the existing configuration instead of creating a tunnel.
1. Add or update unit tests for the route and catch-all invariants.
1. Run `uv run python -m unittest discover -s tests` from `pulumi/`, then run `task pulumi:preview` from the repository root. Review the full preview, especially import/update/delete actions. Never run `task pulumi:up` without explicit authorization to apply the reviewed plan.
1. After any authorized apply, read the Cloudflare configuration back and verify it matches the declared ingress rules. A successful Pulumi command alone is not proof that Cloudflare converged.

## Secret Handling

Set `cloudflare:apiToken` with Pulumi's secret prompt or another non-echoing secret path. Never commit token values, put them in `Pulumi.*.yaml` as plaintext, paste them into chat, or include them in command logs.
