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

The program needs a Cloudflare account ID, the `faerun-argocd` tunnel ID, and an API token. IDs are ordinary configuration; the token must be a secret.

#### Pulumi Cloud dashboard (recommended)

Create or edit an ESC environment in the Pulumi Cloud dashboard. In its Document view, add:

```yaml
values:
  pulumiConfig:
    cloudflare:accountId: <ACCOUNT_ID>
    cloudflare:argocdTunnelId: <TUNNEL_ID>
    cloudflare:apiToken:
      fn::secret: <CLOUDFLARE_API_TOKEN>
```

Save the environment, then link it to the `faerun/prod` stack from `pulumi/`:

```bash
pulumi stack select <ORG>/faerun/prod
pulumi config env add <FULL_ESC_ENVIRONMENT_NAME>
```

The stack's environment reference is configuration, not the token. ESC requires the stack to use the Pulumi Cloud backend.

#### Direct stack configuration alternative

From `pulumi/`, set the public IDs and enter the token at Pulumi's secret prompt:

```bash
pulumi config set cloudflare:accountId <ACCOUNT_ID>
pulumi config set cloudflare:argocdTunnelId <TUNNEL_ID>
pulumi config set --secret cloudflare:apiToken
```

The token should be scoped to the Cloudflare account that owns the tunnels and have **Cloudflare Tunnel Read** and **Cloudflare Tunnel Write** permissions. It does not need DNS permissions. Never paste the token into chat or store it in plaintext in this repository.

The Cloudflare provider imports the existing tunnel config using `<account_id>/<tunnel_id>`. Review the preview's import and route diff before the first apply. Add each additional remotely managed tunnel to `REMOTE_TUNNELS`, configure its ID in the stack or ESC environment, and add tests for its complete ingress configuration.

## Existing AWS resources

The Pulumi project also manages AWS resources for Home Assistant, Route 53, and cert-manager credentials. Cloudflare and AWS resources share the existing Pulumi project and stack; previews therefore require both providers' credentials.

## Tear down

```bash
task pulumi:destroy
```

Destroy removes every resource managed by the selected stack. Do not use it as a cleanup or troubleshooting command.
