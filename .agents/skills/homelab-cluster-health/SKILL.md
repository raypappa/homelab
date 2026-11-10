---
name: homelab-cluster-health
description: Run the homelab Kubernetes and Argo health check.
version: 0.2.0
author: Craig (raypappa), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [homelab, Kubernetes, Argo CD, health]
    related_skills: []
---

# Homelab Cluster Health

Run the repository's read-only health check once and report its actual results. It covers Kubernetes nodes, `kube-system` pods, Argo CD applications, configured app pods, and app-config coverage. For unhealthy pods, it can include bounded recent log excerpts and container/condition details. Do not repair or mutate the cluster as part of a health check.

## When to Use

- Craig asks for a homelab cluster or app health check.
- Craig asks to check Kubernetes or Argo CD health in this repository.

Do not use this workflow to change cluster state, grant RBAC, restart workloads, sync Argo CD, or apply manifests.

## Prerequisites

- Work from the repository root containing `Taskfile.yaml` and `scripts/health_check.py`.
- `task` and `uv` are available; dependencies required by the project are installed.
- The current Kubernetes context, or the context explicitly selected for the command, can read nodes, pods, pod logs, and Argo CD Applications. A denied check is incomplete; do not infer that the unobservable resources are healthy or change RBAC as part of this workflow.
- Keep kubeconfig and credential output private. The checker redacts common credential patterns, but its output is not guaranteed safe to share without review.

## How to Run

Run exactly one check through the repository task:

```text
terminal(command="task health:check", workdir="<repository root>", timeout=180)
```

Use JSON when structured output is useful:

```text
terminal(command="task health:check:json", workdir="<repository root>", timeout=180)
```

The current kubeconfig context is used by default. To select a context, pass the script argument through Task:

```text
terminal(command="task health:check -- --context <context>", workdir="<repository root>", timeout=180)
```

## Procedure

1. Identify the repository root and confirm the intended Kubernetes context. Do not print kubeconfig contents or tokens.
1. Run one health-check task. Do not preface it with a pile of manual `kubectl` or Argo commands.
1. Read the full report and exit code. Report each check's actual status and useful details, including log excerpts only as observed.
1. If access is denied or configuration cannot load, name the incomplete check or configuration error. Do not report an incomplete check as healthy.
1. Stop after reporting unless Craig asks for diagnosis or a fix.

## Pitfalls

- The checker compares pods against configured app namespaces; it is not an external uptime probe.
- Log collection is bounded and only requested for unhealthy containers. It may reveal sensitive workload output despite common-pattern redaction.
- An `OutOfSync` Argo application can still report `Healthy`; report sync and health states separately.
- A log's final error is evidence, not necessarily the root cause. Mark an unresolved trigger as unknown.

## Verification

- Exit code `0`: the checker found no failed health checks.
- Exit code `1`: one or more checks failed; report the findings.
- Exit code `2`: kubeconfig could not be loaded; no health conclusion is supported.

A complete result includes the reported overall status, every check's status and details, the exit code, and any access limitation. Say “healthy” only when the checker reports it and the requested checks ran without access errors.
