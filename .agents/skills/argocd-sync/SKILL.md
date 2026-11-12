---
name: argocd-sync
description: Trigger an Argo CD sync with the homelab identity.
version: 0.1.0
author: Craig (raypappa), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [homelab, Argo CD, sync, deployment]
    related_skills: []
---

# Argo CD Sync

Use the dedicated `sasha-sync` Argo CD API account to trigger syncs for homelab Applications in the `default` project. This workflow assumes Argo CD RBAC has reconciled and the runtime has a secure way to provide the API token; it does not grant Kubernetes write access or store credentials in this repository.

## When to Use

- Craig explicitly asks to sync a named homelab Argo CD Application.
- Craig asks to provision or rotate the `sasha-sync` API token.

Do not sync applications as part of a health check or without an explicit request.

## Prerequisites

- The Argo CD config in `kubernetes/main/bootstrap/argocd/patches/` has reconciled.
- The Argo CD CLI or an approved Argo CD API/MCP integration is configured for the homelab server.
- The `sasha-sync` token is retrieved from the approved secret manager at runtime, never from Git, chat, or logs.

## Token Provisioning

After the account configuration has reconciled, an Argo CD administrator generates a finite-lived token:

```text
argocd account generate-token --account sasha-sync --expires-in 30d
```

Store the generated value in the existing 1Password vault as item `sasha-argocd`, field `token`. The runtime reference is `op://my/sasha-argocd/token`. Do not commit the token, paste it into chat, or include it in command logs. Re-generate and replace the stored value before it expires. Do not omit `--expires-in` or use a non-expiring token.

The CLI/API runtime should inject the stored value as `ARGOCD_AUTH_TOKEN` (or the equivalent secure credential mechanism). Do not put the token value in Hermes configuration or this skill.

## Procedure

1. Confirm the requested Application belongs to the `default` project. The ApplicationSet assigns current and future homelab apps to that project.
1. Confirm the Argo CD CLI/API integration is authenticated as `sasha-sync`; never fall back to the Kubernetes service-account identity or an administrator identity.
1. Trigger the requested Application sync using the approved CLI/API tool. Specify only the named Application; do not sync every app unless Craig explicitly requests that scope.
1. Read back the Application's sync/health state and report the actual result. A successful request is not proof that reconciliation completed.

## Permissions and Effects

- `policy.default` remains `role:readonly`; this account therefore retains the existing read-only baseline and gains only the explicit `applications, sync` write action on `default/*`.
- The policy does not grant `update`, `delete`, `override`, or arbitrary manifest/revision submission.
- Sync applies the Application's configured desired state. The homelab ApplicationSet enables `Prune=true`, so a sync can delete resources removed from an app's desired manifests. Treat sync as a deployment operation.
- This account is separate from the `sasha` Kubernetes ServiceAccount used for cluster inspection. Kubernetes RBAC is not an alternative way to grant Argo CD sync-only access.

## Verification

- Confirm the API token is stored only in the secret manager and its expiration is known.
- Check that `sasha-sync` can sync a `default/<app>` Application but cannot update or delete Applications or use override.
- Confirm the requested Application's final sync and health status from Argo CD after the operation completes.
