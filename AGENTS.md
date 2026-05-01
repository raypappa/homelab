# AGENTS.md

## Repository purpose

This repository manages a homelab as infrastructure-as-code across several layers:

- **Ansible** bootstraps and configures hosts, including K3s control plane and agents.
- **Argo CD + ApplicationSet** take over ongoing Kubernetes app deployment after bootstrap.
- **Kubernetes manifests** live under `kubernetes/main`, mostly as Kustomize trees with Helm chart integration.
- **AWS CDK** provisions AWS-side resources used by the homelab and CI.
- **Pulumi** exists as a separate Python workspace for AWS resources, but the checked-in code is currently small/scaffold-like compared with the Ansible/Kubernetes/CDK portions.

The high-level control flow is explicitly described in `README.md`: Ansible configures hosts and bootstraps Kubernetes and Argo CD first; after that, additional cluster work should be managed by Argo CD.

## First places to look

- `Taskfile.yaml` — top-level entrypoint for almost every routine command.
- `.taskfiles/ansible/Taskfile.yaml` — Ansible lint/deploy/canary/diff/setup commands.
- `.taskfiles/cdk/Taskfile.yaml` — CDK install/test/synth/diff/deploy commands.
- `.taskfiles/argocd/Taskfile.yaml` — Argo CD bootstrap applies.
- `.taskfiles/pulumi/Taskfile.yaml` — Pulumi up/preview/destroy wrappers.
- `kubernetes/main/bootstrap/appset.yaml` — ApplicationSet generator and rolling sync strategy.
- `scripts/dependency_graph.py` — enforces and rewrites Argo app dependency waves from `config.json` files.
- `ansible/homelab.yaml` — orchestrates host roles and deployment order.

## Tooling and environment

Observed toolchain and versions/config:

- **Task** is the primary command runner.
- **uv** is the Python environment/dependency manager (`task configure:uv`, `uv sync --all-packages`).
- **pnpm** is used for Node dependencies; workspace members are `.` and `cdk` (`pnpm-workspace.yaml`).
- **Node/pnpm**:
  - root `.mise.toml` installs `node = latest` and `pnpm = 10.30.2`
  - `cdk/package.json` additionally declares `node 24.7.0` and `pnpm 10.30.2`
- **Python**:
  - root `pyproject.toml` requires `>=3.13,<4`
  - root uv workspace includes `pulumi`
- **Formatting/linting** is enforced mostly via pre-commit, Biome, yamlfmt, yamllint, ansible-lint, cspell, and mdformat.

## Essential commands

Run these from the repository root unless the task wrapper changes directories for you.

### Setup

```bash
task configure
```

What it does:

- `task cdk:configure` → `pnpm install` in `cdk/`
- `task configure:uv` → `uv sync --all-packages`
- `task ansible:configure` → `uv run ansible-galaxy install -r galaxy.yaml`

If you only need Python deps:

```bash
task configure:uv
```

### Repo-wide checks

```bash
task check
pre-commit run -a
```

`task check` runs Ansible lint plus `pre-commit run -a`.

### Kubernetes / Kustomize

Build every checked-in kustomization, including Helm-backed ones:

```bash
task build:kustomize
```

Important: this uses:

```bash
kustomize build --enable-helm <dir>
```

So local verification needs both **kustomize** and **helm** installed.

### Argo CD bootstrap

```bash
task argocd:deploy
task argocd:deploy:argocd
task argocd:deploy:appset
```

These are plain `kubectl apply -f ...` wrappers over `kubernetes/main/bootstrap/argocd.yaml` and `appset.yaml`.

### Ansible

Lint:

```bash
task ansible:check
```

Install required roles/collections:

```bash
task ansible:configure
```

Ping hosts:

```bash
task ansible:deploy:canary
```

Run the playbook:

```bash
task ansible:deploy -- <extra ansible-playbook args>
```

Dry-run diff:

```bash
task ansible:diff
```

CI-oriented variants exist (`deploy:ci`, `deploy:canary:ci`, `diff:ci`) and expect bastion-related vars such as `BASTION_HOST`, `BASTION_PORT`, and `BASTION_USER`.

### AWS CDK

```bash
task cdk:configure
task cdk:test:unit
task cdk:synth
task cdk:diff
task cdk:deploy
task cdk:deploy:ci
task cdk:bootstrap
```

Implementation details:

- `task cdk:configure` runs `pnpm install` in `cdk/`
- `task cdk:test:unit` runs `pnpm run test`
- `task cdk:synth/diff/deploy/...` all funnel through `pnpm exec cdk`

### Pulumi

```bash
task pulumi:preview
task pulumi:up
task pulumi:destroy
```

These are wrappers around `uv run pulumi ...` inside `pulumi/`.

## Architecture and control flow

### 1. Host bootstrap and cluster creation

`ansible/homelab.yaml` is the orchestration root.

Notable behavior:

- `headscale` is intentionally deployed first. The playbook comments warn that bringing up Tailscale agents before Headscale is working breaks bootstrap.
- `common_critical` and `common` are run before broader host configuration.
- K3s control plane and agents are split into separate roles.
- TURN/STUN, game server, and NFS are managed as separate role targets.

Representative implementation details:

- `ansible/roles/common/tasks/main.yml` installs a large baseline package set, configures users, conditionally installs Tailscale, and can trigger hostname changes.
- `ansible/roles/k3s_controlplane/tasks/cluster.yml` templates K3s config/service files and restarts/enables the `k3s` systemd service.
- `ansible/roles/k3s_controlplane/tasks/argocd.yml` waits for K3s, creates the `argocd` namespace, then applies the Argo CD bootstrap using `k3s kubectl kustomize --enable-helm ... | k3s kubectl apply -f -`.

### 2. Argo CD bootstrap and steady-state app delivery

Once the cluster exists, Argo CD becomes the desired-state engine.

- `kubernetes/main/bootstrap/argocd.yaml` defines the self-managing Argo CD `Application` pointed back at this repo.
- `kubernetes/main/bootstrap/appset.yaml` defines an `ApplicationSet` that scans `kubernetes/main/apps/**/config.json`.
- Each app directory supplies its own `config.json` metadata plus its own `kustomization.yaml`/values/manifests.

The non-obvious part is the sync ordering:

- `config.json` contains a `dependencies` array and a `wave` value.
- The `dependencies` array lists apps that must deploy before the current app, typically to ensure custom resource definitions (CRDs) are available. For example, an app using a `ReplicationDestination` (from volsync) lists `volsync` as a dependency.
- `scripts/dependency_graph.py` loads every app config, validates dependency names, computes dependency groups, rewrites each app's `wave`, and verifies that `appset.yaml`'s `rollingSync.steps` include the maximum computed wave.
- A local pre-commit hook (`local-config-change`) runs this script whenever `config.json` files change.

If you add or rename app dependencies, expect wave numbers to be rewritten automatically and `appset.yaml` to become invalid if its rolling sync steps do not cover the new max wave.

### 3. Kubernetes app layout

The common Kubernetes pattern is:

- one app per directory under `kubernetes/main/apps/<category>/<app>/`
- `config.json` holds Argo metadata
- `kustomization.yaml` assembles raw resources and/or Helm charts
- `values.yaml` or app-specific values files customize charts

Observed example:

- `kubernetes/main/apps/media/jellyfin/config.json` defines `destNamespace`, `appName`, `group`, `dependencies`, `serverSideApply`, `ignoreDifferences`, and `wave`
- `kubernetes/main/apps/media/jellyfin/values.yaml` uses the bjw-s `app-template` chart style with `controllers`, `persistence`, `service`, and hardened `securityContext` settings
- `kubernetes/main/apps/selfhosted/tube-archivist/kustomization.yaml` shows the mixed pattern of `helmCharts:` plus many raw `resources:` entries

#### External-DNS integration

Apps that need external DNS records use a LoadBalancer service with external-dns annotations. The pattern is:

```yaml
service:
  app:
    type: LoadBalancer
    annotations:
      metallb.universe.tf/address-pool: metalpool
      external-dns.alpha.kubernetes.io/hostname: radarr.stoneydavis.local
      external-dns.alpha.kubernetes.io/ttl: '1800'
      external-dns.alpha.kubernetes.io/webhook-comment: k8s_managed
      external-dns.alpha.kubernetes.io/webhook-match-subdomain: 'true'
      external-dns.alpha.kubernetes.io/webhook-disabled: 'false'
    externalTrafficPolicy: Cluster
    ports:
      http:
        port: 80
        targetPort: 9696
```

External-DNS (`kubernetes/main/apps/system/external-dns`) watches for services with these annotations and automatically creates DNS records. It does not need to be listed in app `dependencies` since it works passively by watching service annotations. Examples: `kubernetes/main/apps/downloads/radarr`, `kubernetes/main/apps/downloads/prowlarr`, `kubernetes/main/apps/downloads/readarr`.

### 4. AWS-side infrastructure

`cdk/` is the active TypeScript AWS CDK project.

Observed pattern:

- `cdk/cdk.json` runs the app through `pnpm exec ts-node --prefer-ts-exts bin/cdk.ts`
- context values in `cdk/cdk.json` are important; `githubMap` is consumed in code and many AWS CDK feature flags are set there
- `cdk/lib/stacks/githubOIDC.ts` uses `this.node.tryGetContext("githubMap")` to create a GitHub OIDC provider and IAM role for GitHub Actions

`pulumi/` is present as a uv workspace package. It currently contains a small amount of real component code (`pulumi/stacks/weasel.py`) alongside template-like files (`pulumi/main.py`, `pulumi/README.md`). Treat it as a separate Python IaC surface, but verify whether a given change belongs in Pulumi or CDK before editing.

## Style and file conventions

### YAML

YAML style is enforced strongly:

- document start `---` is required (`.yamllint.yaml`)
- yamlfmt uses LF line endings, block array style, max line length 80, and retains line breaks (`.yamlfmt.yaml`)
- quoted strings prefer double quotes when needed (`.yamllint.yaml`)

Many YAML files include `yaml-language-server` schema comments at the top. Preserve them.

### TypeScript / JSON / JS / CSS

Biome is configured with:

- spaces, width 2
- LF line endings
- organize imports enabled

The repo runs a local pre-commit Biome check in write mode for matching file types.

### Python

Python packaging is managed by uv. The checked-in Python code uses straightforward typing and 4-space indentation. No formatter configuration beyond pre-commit-visible tooling was found in the files reviewed.

### Ansible

Observed conventions:

- role task files are split by concern and referenced via `include_tasks` / `include_role`
- many files declare ansible-lint YAML schemas in comments; preserve them
- task names commonly use a `Role | Action` style in more focused task files
- `ansible/roles/.../tasks` mix `.yml` and `.yaml`; follow the existing filename in the area you touch rather than normalizing

## Testing and validation expectations

Use the narrowest relevant command first, then broader checks.

- **Ansible changes**: `task ansible:check`
- **Kubernetes manifest changes**: `task build:kustomize`
- **CDK changes**: `task cdk:test:unit`, then `task cdk:synth`, optionally `task cdk:diff`
- **Pulumi changes**: `task pulumi:preview`
- **Docs / repo-wide / mixed config changes**: `pre-commit run -a` or at minimum the relevant hooks

Useful CI signals from checked-in workflows:

- `.github/workflows/kustomize.yaml` validates all Kustomize trees with Helm enabled
- `.github/workflows/cdk.yaml` runs CDK configure, bootstrap, unit tests, synth, diff, and deploy-on-main
- `.github/workflows/biome.yaml` runs `biome ci .`
- `.github/workflows/ansible.yaml` and `ansible-scheduled.yaml` gate or execute Ansible based on changed files and environment setup

## Important gotchas

### Argo CD app-of-apps constraints

Per `README.md`:

- self-referential Argo CD Applications/App-of-Apps must live in the default `AppProject`
- deleting a self-referential App-of-Apps may require manually removing the finalizer after other resources are gone

### Dependency waves are not manual bookkeeping

Do not hand-edit app `wave` values without understanding `scripts/dependency_graph.py`; the script rewrites them from dependency relationships and pre-commit enforces that behavior.

Also note the script currently looks for files named `config.json` and `config.disabled.json` in code, while the repo’s pre-commit regex also mentions `config.json.disabled`. Verify the actual filename pattern already used in the target area before introducing disabled configs.

### Helm-backed Kustomize is standard here

`task build:kustomize` and the Ansible Argo CD bootstrap both rely on `--enable-helm`. If a Kustomize build fails locally, missing Helm support is one of the first things to verify.

### Root `package.json` is mostly tooling, not an app

The root Node package is for repo tooling (Biome, cspell). The actual TypeScript application code is in `cdk/`.

### CI Ansible execution has extra network assumptions

The CI/scheduled workflows set up Tailscale, AWS credentials, a bastion SSH path, and sometimes SSH port forwarding to reach the cluster. A local command that works on the maintainer machine may still fail in CI if it assumes different network reachability.

### Tunnel management is partly scripted, partly manual

`README.md` says `scripts/setup-tunnel.sh` handles most tunnel setup steps, but **not** the Cloudflare Application creation step. The script also writes a 1Password document via `op.exe`, so it assumes that CLI/tooling environment.

## What not to assume

Only the following are clearly observed:

- Task is the canonical command entrypoint
- uv and pnpm are both required
- Argo app ordering depends on `config.json` metadata plus the dependency graph script
- Kustomize builds need Helm enabled
- CDK is the main TypeScript codebase; Pulumi is present but comparatively smaller/scaffold-like

No additional local-only deploy commands, dev servers, or custom formatting/lint commands were found beyond the checked-in Taskfiles, pre-commit config, and CI workflows.
