# AGENTS.md

## Repository purpose

This repository manages a homelab as infrastructure-as-code across several layers:

- **Ansible** bootstraps and configures hosts, including K3s control plane and agents.
- **Argo CD + ApplicationSet** take over ongoing Kubernetes app deployment after bootstrap.
- **Kubernetes manifests** live under `kubernetes/main`, mostly as Kustomize trees with Helm chart integration.
- **AWS CDK** provisions AWS-side resources used by the homelab and CI.
- **Pulumi** exists as a separate Python workspace for AWS resources; currently contains minimal checked-in code.

**Control Flow**: Ansible configures hosts and bootstraps Kubernetes and Argo CD first. After bootstrap, all cluster deployments are managed by Argo CD (described in `README.md`).

**For newcomers**: Start with the [First places to look](#first-places-to-look) section, then read the [Architecture and control flow](#architecture-and-control-flow) section.

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

Initialize all dependencies (required once per checkout):

```bash
task configure
```

This runs:

- `task cdk:configure` → `pnpm install` in `cdk/`
- `task configure:uv` → `uv sync --all-packages`
- `task ansible:configure` → `uv run ansible-galaxy install -r galaxy.yaml`

For Python dependencies only:

```bash
task configure:uv
```

### Validation and Checks

Lint and check all code:

```bash
task check
pre-commit run -a
```

What `task check` does:

- Runs `ansible-lint` on Ansible code
- Runs `pre-commit run -a` (Biome, yamlfmt, cspell, mdformat, etc.)

### Kubernetes / Kustomize

Build all Kustomize trees with Helm enabled:

```bash
task build:kustomize
```

Equivalent to:

```bash
kustomize build --enable-helm <dir>
```

**Important**: Local verification requires both **kustomize** and **helm** installed.

### Argo CD bootstrap

Deploy Argo CD to the cluster:

```bash
task argocd:deploy
task argocd:deploy:argocd
task argocd:deploy:appset
```

These are plain `kubectl apply -f ...` wrappers over:

- `kubernetes/main/bootstrap/argocd.yaml` — self-managing Argo CD Application
- `kubernetes/main/bootstrap/appset.yaml` — ApplicationSet with rolling sync strategy

### Ansible

Lint Ansible code:

```bash
task ansible:check
```

Install Ansible roles and collections:

```bash
task ansible:configure
```

Ping all hosts (canary check):

```bash
task ansible:deploy:canary
```

Run the main playbook:

```bash
task ansible:deploy -- <extra ansible-playbook args>
```

Dry-run diff (shows what would change):

```bash
task ansible:diff
```

**CI variants** exist for bastion-based deployments: `deploy:ci`, `deploy:canary:ci`, `diff:ci`. These expect environment variables: `BASTION_HOST`, `BASTION_PORT`, `BASTION_USER`.

### AWS CDK

```bash
task cdk:configure      # Install dependencies
task cdk:test:unit      # Run unit tests
task cdk:synth          # Generate CloudFormation template
task cdk:diff           # Show changes (dry-run)
task cdk:deploy         # Deploy stack
task cdk:deploy:ci      # Deploy via CI/CD
task cdk:bootstrap      # Bootstrap AWS account
```

**Implementation details**:

- `task cdk:configure` runs `pnpm install` in `cdk/`
- `task cdk:test:unit` runs `pnpm run test`
- `task cdk:synth/diff/deploy/...` all funnel through `pnpm exec cdk`

### Pulumi

```bash
task pulumi:preview     # Show planned changes
task pulumi:up          # Deploy stack
task pulumi:destroy     # Destroy stack
```

Wrappers around `uv run pulumi ...` executed inside `pulumi/` directory.

## Architecture and control flow

### 1. Host bootstrap and cluster creation

`ansible/homelab.yaml` orchestrates all host configuration.

**Key behaviors**:

- `headscale` is intentionally deployed first—starting Tailscale agents before Headscale is working breaks bootstrap
- `common_critical` and `common` roles run before other host configuration
- K3s control plane and agents deployed separately
- TURN/STUN, game server, and NFS managed as separate role targets

**Representative implementation details**:

- `ansible/roles/common/tasks/main.yml` — installs base packages, configures users, conditionally installs Tailscale, can trigger hostname changes
- `ansible/roles/k3s_controlplane/tasks/cluster.yml` — templates K3s config/service files, restarts/enables `k3s` systemd service
- `ansible/roles/k3s_controlplane/tasks/argocd.yml` — waits for K3s, creates `argocd` namespace, applies Argo CD bootstrap via: `k3s kubectl kustomize --enable-helm ... | k3s kubectl apply -f -`

### 2. Argo CD bootstrap and steady-state app delivery

Once the cluster exists, Argo CD becomes the desired-state engine.

**Bootstrap manifests**:

- `kubernetes/main/bootstrap/argocd.yaml` — defines self-managing Argo CD `Application` pointed at this repo
- `kubernetes/main/bootstrap/appset.yaml` — defines `ApplicationSet` that discovers apps via `kubernetes/main/apps/**/config.json`

**App synchronization and dependency ordering**:

Each app directory provides:

- `config.json` — Argo CD metadata including `dependencies`, `wave`, `destNamespace`, etc.
- `kustomization.yaml` — resource assembly
- `values.yaml` or chart-specific values

**Dependency management** (the non-obvious part):

- `config.json` contains a `dependencies` array listing apps that must deploy before the current app (e.g., an app using `ReplicationDestination` from volsync lists `volsync` as a dependency)
- `config.json` also contains a `wave` value for sync ordering
- `scripts/dependency_graph.py` loads every app config, validates dependency names, computes dependency groups, **rewrites each app's `wave`**, and verifies that `appset.yaml`'s `rollingSync.steps` cover the maximum computed wave
- A pre-commit hook (`local-config-change`) enforces this: `config.json` changes trigger automatic wave rewriting

**Critical**: Do not hand-edit `wave` values. The script computes and rewrites them from `dependencies`.

### 3. Kubernetes app layout

Standard app directory structure:

```
kubernetes/main/apps/<category>/<app>/
├── config.json         # Argo metadata (dependencies, wave, namespace, etc.)
├── kustomization.yaml  # Resource assembly and Helm chart integration
└── values.yaml         # Helm chart values customization
```

**Examples**:

- `kubernetes/main/apps/media/jellyfin/` — uses bjw-s `app-template` chart with hardened `securityContext`
- `kubernetes/main/apps/selfhosted/tube-archivist/` — mixes `helmCharts:` with raw `resources:`

#### External-DNS integration

Apps needing external DNS records use LoadBalancer services with external-dns annotations:

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

External-DNS (`kubernetes/main/apps/system/external-dns`) watches for services with these annotations and automatically creates DNS records. **No need to list external-dns in app dependencies**—it works passively by watching service annotations.

Examples: `radarr`, `prowlarr`, `readarr`

### 4. AWS-side infrastructure

**AWS CDK** (`cdk/` directory) is the active TypeScript IaC surface.

Observed patterns:

- `cdk/cdk.json` runs the app through `pnpm exec ts-node --prefer-ts-exts bin/cdk.ts`
- Context values in `cdk/cdk.json` are important; `githubMap` is consumed in code
- AWS CDK feature flags are set in `cdk.json`
- `cdk/lib/stacks/githubOIDC.ts` uses `this.node.tryGetContext("githubMap")` to create GitHub OIDC provider and IAM role for GitHub Actions

**Pulumi** (`pulumi/` directory) is a separate Python IaC workspace.

Currently contains:

- `pulumi/stacks/weasel.py` — real component code
- `pulumi/main.py`, `pulumi/README.md` — template/scaffold files

**Guidance**: Verify whether a given change belongs in Pulumi or CDK before editing. Treat Pulumi as a secondary, experimental surface compared with the primary CDK codebase.

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

Use the narrowest relevant command first, then broaden to build confidence.

| Change Type           | Validation         | Command                                |
| --------------------- | ------------------ | -------------------------------------- |
| Ansible               | Linting            | `task ansible:check`                   |
| Kubernetes manifests  | Kustomize build    | `task build:kustomize`                 |
| CDK                   | Unit tests + synth | `task cdk:test:unit && task cdk:synth` |
| Pulumi                | Preview            | `task pulumi:preview`                  |
| Docs / config / mixed | Repo-wide          | `pre-commit run -a`                    |

**CI signals** (checked-in workflows):

- `.github/workflows/kustomize.yaml` — validates all Kustomize trees with Helm enabled
- `.github/workflows/cdk.yaml` — configure, bootstrap, unit tests, synth, diff, deploy-on-main
- `.github/workflows/biome.yaml` — `biome ci .`
- `.github/workflows/ansible.yaml` and `ansible-scheduled.yaml` — gate/execute Ansible based on changed files and env

## Important gotchas

## Important gotchas

### Argo CD app-of-apps constraints

Self-referential Argo CD Applications/App-of-Apps must live in the default `AppProject`. Deleting self-referential app-of-apps may require manually removing the finalizer after other resources are cleaned up.

**Note**: Reconfiguring Argo CD to support [applications in any namespace](https://argo-cd.readthedocs.io/en/stable/operator-manual/app-any-namespace/) would resolve this, but has not been implemented.

### Dependency waves are automatically managed

**Do not hand-edit `wave` values.** The `scripts/dependency_graph.py` script computes and rewrites them from `dependencies` relationships. Pre-commit enforces this behavior.

**Configuration filename patterns**: The script looks for `config.json` and `config.disabled.json`. The pre-commit regex also mentions `config.json.disabled`. Verify the filename pattern already used in the target area before introducing disabled configs.

### Helm-backed Kustomize is standard

Both `task build:kustomize` and the Ansible Argo CD bootstrap rely on `--enable-helm`. If a Kustomize build fails locally, missing Helm support is one of the first things to verify.

### Root `package.json` is tooling-only

The root Node package manages repo tooling (Biome, cspell). The actual TypeScript application code lives in `cdk/`.

### CI Ansible execution has extra network assumptions

CI/scheduled workflows set up Tailscale, AWS credentials, bastion SSH paths, and sometimes SSH port forwarding to reach the cluster. A local command that works on the maintainer machine may still fail in CI if it assumes different network reachability.

### Tunnel management is partly scripted, partly manual

`scripts/setup-tunnel.sh` handles most tunnel setup steps, but **not** the Cloudflare Application creation (auth/authorization policy). The script also uses 1Password CLI (`op.exe`), so it assumes that tooling environment.

## What not to assume

Only the following are clearly observed:

- Task is the canonical command entrypoint
- uv and pnpm are both required
- Argo app ordering depends on `config.json` metadata plus the dependency graph script
- Kustomize builds need Helm enabled
- CDK is the main TypeScript codebase; Pulumi is present but comparatively smaller/scaffold-like

No additional local-only deploy commands, dev servers, or custom formatting/lint commands were found beyond the checked-in Taskfiles, pre-commit config, and CI workflows.
