# Pulumi

The Python Pulumi project manages the homelab's AWS resources and remotely managed Cloudflare Tunnel configurations. The checked-in Cloudflare registry currently adopts the Argo CD tunnel; other Cloudflare UI-managed tunnels can be added incrementally.

## Preview and apply

```bash
task pulumi:preview
task pulumi:up
```

Always review the complete preview before applying it. The first update imports the existing Argo CD tunnel configuration into Pulumi and applies the declared ingress route. This PR does not run `pulumi up` or change live Cloudflare or cluster state.

## Cloudflare Tunnel configuration

`stacks/cloudflare_tunnels.py` manages only tunnels whose configuration source is Cloudflare (`config_src: cloudflare`). Local-config tunnels stay managed by their Kubernetes `cloudflared` deployment. Each registry entry carries the complete configuration object supported by the pinned Pulumi Cloudflare provider, including `ingresses` and any top-level `origin_request`. Cloudflare replaces the entire configuration when it updates a tunnel, so inspect and preserve route order, per-ingress origin settings, top-level origin settings, and the final catch-all before adding a tunnel.

Cloudflare provider v6.24.0 does not model the API's top-level `warp-routing` field. The live Argo CD tunnel has `warp-routing.enabled: false`; this observed but unmanaged value is recorded in the registry. Do not add a tunnel with WARP routing enabled until the provider supports it, and do not apply if preview shows an unexpected WARP-routing change.

The current Argo CD route preserves `argocd.fieldsofbears.com` and points to `https://argocd-server.argocd.svc.cluster.local:443`, with `argocd.internal.stoneydavis.com` as the expected origin certificate name and TLS verification enabled. The registry includes the required `http_status:404` catch-all. The separate `faerun-game-server` remote tunnel remains outside Pulumi for a later migration.

### Required stack configuration

`Pulumi.prod.yaml` contains the production configuration as an inline Pulumi ESC environment. It imports `faerun/1password`, which must expose `1passwordToken` as a secret; ESC uses that token to read the Cloudflare account ID and API token from the listed 1Password item. The nonsecret Argo CD tunnel ID, AWS region, and existing `faerun:weasel` values are also declared in the file.

The values under `environment.values.pulumiConfig` become Pulumi stack configuration. The Cloudflare API token is passed as the provider's secret `cloudflare:apiToken`; it is resolved from 1Password at environment-open time and is not stored in the repository. The 1Password item paths are references, not secret values. The `1password-secrets` ESC provider is currently in preview.

ESC integration requires the Pulumi Cloud backend. From `pulumi/`, select the production stack and preview:

```bash
pulumi stack select <ORG>/faerun/prod
pulumi preview
```

The Cloudflare API token should be scoped to the account that owns the tunnels and have **Cloudflare Tunnel Read** and **Cloudflare Tunnel Write** permissions. It does not need DNS permissions. Never paste the token into chat or commit its value to this repository.

The Cloudflare provider imports the existing tunnel config using `<account_id>/<tunnel_id>`. Review the preview's import and route diff before the first apply. To add another remotely managed tunnel, add it to `REMOTE_TUNNELS`, give it a stack-config key for its tunnel ID in `Pulumi.prod.yaml`, and add tests for its complete ingress configuration.

## Existing AWS resources

The Pulumi project also manages AWS resources for Home Assistant, Route 53, and cert-manager credentials. Cloudflare and AWS resources share the existing Pulumi project and stack; previews therefore require both providers' credentials.

## Tear down

```bash
task pulumi:destroy
```

Destroy removes every resource managed by the selected stack. Do not use it as a cleanup or troubleshooting command.
