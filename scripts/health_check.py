#!/usr/bin/env python3
"""Health checks for Kubernetes cluster and Argo CD applications.

Reads cluster state via the Kubernetes API and reports on:
  - Node health (Ready, Schedulable)
  - System pod health (kube-system namespace)
  - Argo CD application sync/health status (via Application CRD)
  - Per-application pod readiness across managed namespaces

Exit codes:
  0 — all checks passed
  1 — one or more checks failed
  2 — connection or configuration error
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

from kubernetes import client, config
from kubernetes.client.rest import ApiException

if TYPE_CHECKING:
    from kubernetes.client.models.v1_node import V1Node
    from kubernetes.client.models.v1_pod import V1Pod
    from kubernetes.client.models.v1_node_condition import V1NodeCondition

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARGOCD_NAMESPACE = "argocd"
SYSTEM_NAMESPACE = "kube-system"
APPS_DIR = pathlib.Path("kubernetes/main/apps")

# Colors (disabled when output is not a TTY)
_USE_COLOR = sys.stdout.isatty()


class _C:
    """ANSI color codes."""

    RED = "\033[91m" if _USE_COLOR else ""
    GREEN = "\033[92m" if _USE_COLOR else ""
    YELLOW = "\033[93m" if _USE_COLOR else ""
    CYAN = "\033[96m" if _USE_COLOR else ""
    BOLD = "\033[1m" if _USE_COLOR else ""
    DIM = "\033[2m" if _USE_COLOR else ""
    RESET = "\033[0m" if _USE_COLOR else ""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class Status(Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class CheckResult:
    name: str
    status: Status
    details: list[str] = field(default_factory=list)


@dataclass
class Report:
    cluster_name: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def overall(self) -> Status:
        statuses = [r.status for r in self.results]
        if Status.FAIL in statuses:
            return Status.FAIL
        if Status.WARN in statuses:
            return Status.WARN
        if all(s == Status.SKIP for s in statuses):
            return Status.SKIP
        return Status.OK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_icon(s: Status) -> str:
    return {
        Status.OK: f"{_C.GREEN}●{_C.RESET}",
        Status.WARN: f"{_C.YELLOW}●{_C.RESET}",
        Status.FAIL: f"{_C.RED}●{_C.RESET}",
        Status.SKIP: f"{_C.DIM}○{_C.RESET}",
    }[s]


def _load_config_files() -> dict[str, dict[str, Any]]:
    """Load all active config.json files from kubernetes/main/apps/."""
    apps: dict[str, dict[str, Any]] = {}
    if not APPS_DIR.exists():
        return apps
    for config_path in APPS_DIR.rglob("config.json"):
        try:
            data: dict[str, Any] = json.loads(config_path.read_text())
            apps[data["appName"]] = data
        except (json.JSONDecodeError, KeyError):
            continue
    return apps


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_nodes(v1: client.CoreV1Api) -> CheckResult:
    """Check that all nodes are Ready and Schedulable."""
    result = CheckResult(name="Cluster Nodes", status=Status.OK)
    try:
        nodes: list[V1Node] = v1.list_node().items
    except ApiException as exc:
        result.status = Status.FAIL
        result.details.append(f"API error: {exc.reason}")
        return result

    if not nodes:
        result.status = Status.WARN
        result.details.append("No nodes found in cluster")
        return result

    for node in nodes:
        meta = node.metadata
        status_obj = node.status
        spec_obj = node.spec
        name = meta.name if meta else "<unknown>"
        conditions: list[V1NodeCondition] = (
            status_obj.conditions if status_obj and status_obj.conditions else []
        )
        ready_cond = next((c for c in conditions if c.type == "Ready"), None)
        schedulable = not (spec_obj and spec_obj.unschedulable is True)

        if ready_cond and ready_cond.status == "True":
            if not schedulable:
                result.status = Status.WARN
                result.details.append(f"{name}: Ready but Unschedulable")
        else:
            result.status = Status.FAIL
            ready_val = ready_cond.status if ready_cond else "Unknown"
            result.details.append(f"{name}: NotReady (condition={ready_val})")

    if not result.details:
        result.details.append(f"{len(nodes)} node(s) healthy")
    return result


def check_system_pods(v1: client.CoreV1Api) -> CheckResult:
    """Check that kube-system pods are running and ready."""
    result = CheckResult(name="System Pods", status=Status.OK)
    try:
        pods: list[V1Pod] = v1.list_namespaced_pod(
            namespace=SYSTEM_NAMESPACE,
            field_selector="status.phase!=Running,status.phase!=Succeeded",
        ).items
    except ApiException as exc:
        result.status = Status.FAIL
        result.details.append(f"API error: {exc.reason}")
        return result

    if pods:
        result.status = Status.FAIL
        for pod in pods:
            phase = pod.status.phase if pod.status else "Unknown"
            pod_name = pod.metadata.name if pod.metadata else "<unknown>"
            result.details.append(f"{pod_name}: {phase}")
    else:
        result.details.append(f"All pods running in {SYSTEM_NAMESPACE}")
    return result


def check_argo_apps(
    custom_api: client.CustomObjectsApi,
    config_apps: dict[str, dict[str, Any]],
) -> CheckResult:
    """Check Argo CD Application sync and health status."""
    result = CheckResult(name="Argo CD Apps", status=Status.OK)

    try:
        apps_resource = custom_api.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=ARGOCD_NAMESPACE,
            plural="applications",
        )
    except ApiException as exc:
        result.status = Status.FAIL
        result.details.append(f"API error: {exc.reason}")
        return result

    items = apps_resource.get("items", [])
    if not items:
        result.status = Status.WARN
        result.details.append("No Argo CD applications found")
        return result

    # Sort apps by wave, then by name within each wave
    def _wave_sort_key(app: dict[str, Any]) -> tuple[int, str]:
        name = app.get("metadata", {}).get("name", "")
        wave_str = config_apps.get(name, {}).get("wave", "99")
        try:
            wave_num = int(wave_str)
        except (ValueError, TypeError):
            wave_num = 99
        return (wave_num, name)

    items = sorted(items, key=_wave_sort_key)

    # Skip self-managing argocd apps
    managed_items = [
        a
        for a in items
        if a.get("metadata", {}).get("name", "") not in ("appset", "argocd")
    ]

    for app in managed_items:
        name = app.get("metadata", {}).get("name", "<unknown>")
        status = app.get("status", {})
        sync_status = status.get("sync", {}).get("status", "Unknown")
        health_status = status.get("health", {}).get("status", "Unknown")

        is_unhealthy = health_status not in ("Healthy", "Missing")
        is_out_of_sync = sync_status != "Synced"

        if is_unhealthy or is_out_of_sync:
            result.status = Status.FAIL
            parts = [f"sync={sync_status}", f"health={health_status}"]
            wave = config_apps.get(name, {}).get("wave", "?")
            result.details.append(f"{name} [wave {wave}]: {', '.join(parts)}")

    if not result.details:
        result.details.append(f"{len(managed_items)} app(s) synced and healthy")
    return result


def check_app_pods(
    v1: client.CoreV1Api,
    config_apps: dict[str, dict[str, Any]],
) -> CheckResult:
    """Check pod readiness for each managed application namespace."""
    result = CheckResult(name="App Pods", status=Status.OK)

    # Collect unique namespaces from config (exclude system namespaces)
    namespaces = {
        app["destNamespace"]
        for app in config_apps.values()
        if app.get("destNamespace") not in (SYSTEM_NAMESPACE, ARGOCD_NAMESPACE)
    }

    for ns in sorted(namespaces):
        try:
            pods: list[V1Pod] = v1.list_namespaced_pod(
                namespace=ns,
                field_selector="status.phase!=Succeeded",
            ).items
        except ApiException as exc:
            result.status = Status.WARN
            result.details.append(f"{ns}: API error ({exc.reason})")
            continue

        if not pods:
            continue

        not_ready = []
        for pod in pods:
            pod_status = pod.status
            conditions = (
                pod_status.conditions if pod_status and pod_status.conditions else []
            )
            ready_cond = next((c for c in conditions if c.type == "Ready"), None)
            if ready_cond and ready_cond.status != "True":
                pod_name = pod.metadata.name if pod.metadata else "<unknown>"
                not_ready.append(pod_name)

        if not_ready:
            result.status = Status.FAIL
            result.details.append(
                f"{ns}: {len(not_ready)} not-ready pod(s): " + ", ".join(not_ready)
            )

    if not result.details:
        checked = len(namespaces)
        result.details.append(f"All pods ready across {checked} namespace(s)")
    return result


def check_app_configs(config_apps: dict[str, dict[str, Any]]) -> CheckResult:
    """Validate that deployed apps have config.json entries."""
    result = CheckResult(name="App Config Coverage", status=Status.OK)

    if not config_apps:
        result.status = Status.WARN
        result.details.append("No config.json files found")
        return result

    for name, cfg in config_apps.items():
        missing_fields = [
            f for f in ("appName", "destNamespace", "group", "wave") if f not in cfg
        ]
        if missing_fields:
            result.status = Status.WARN
            result.details.append(
                f"{name}: missing fields: {', '.join(missing_fields)}"
            )

    if not result.details:
        result.details.append(f"{len(config_apps)} app config(s) valid")
    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_report(report: Report) -> None:
    """Print a human-readable report."""
    divider = f"{_C.DIM}{'─' * 60}{_C.RESET}"
    print()
    print(f"{_C.BOLD}Health Check: {report.cluster_name}{_C.RESET}")
    print(divider)

    for result in report.results:
        icon = _status_icon(result.status)
        print(f"  {icon} {_C.BOLD}{result.name}{_C.RESET}")
        for detail in result.details:
            print(f"      {detail}")
    print(divider)

    label = {
        Status.OK: f"{_C.GREEN}HEALTHY{_C.RESET}",
        Status.WARN: f"{_C.YELLOW}DEGRADED{_C.RESET}",
        Status.FAIL: f"{_C.RED}UNHEALTHY{_C.RESET}",
        Status.SKIP: f"{_C.DIM}SKIPPED{_C.RESET}",
    }[report.overall]
    print(f"  Overall: {label}")
    print()


def print_json(report: Report) -> None:
    """Print a machine-readable JSON report."""
    output = {
        "cluster": report.cluster_name,
        "overall": report.overall.value,
        "checks": [
            {
                "name": r.name,
                "status": r.status.value,
                "details": r.details,
            }
            for r in report.results
        ],
    }
    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Health checks for Kubernetes cluster and Argo CD apps.",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="Kubernetes context to use (default: current context)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output report as JSON",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Check only apps in this namespace",
    )
    parser.add_argument(
        "--skip-nodes",
        action="store_true",
        help="Skip node health check",
    )
    parser.add_argument(
        "--skip-argo",
        action="store_true",
        help="Skip Argo CD application check",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Load kubeconfig
    try:
        config.load_kube_config(context=args.context)
    except config.ConfigException as exc:
        print(f"{_C.RED}Failed to load kubeconfig: {exc}{_C.RESET}", file=sys.stderr)
        return 2

    # Derive cluster name from current context
    _, active_context = config.list_kube_config_contexts()
    cluster_name = (
        args.context or active_context.get("name", "unknown")
        if active_context
        else "unknown"
    )

    v1 = client.CoreV1Api()
    custom_api = client.CustomObjectsApi()

    # Load config files for cross-referencing
    config_apps = _load_config_files()

    # Filter by namespace if requested
    if args.namespace:
        config_apps = {
            name: cfg
            for name, cfg in config_apps.items()
            if cfg.get("destNamespace") == args.namespace
        }

    # Build report
    report = Report(cluster_name=cluster_name)

    if not args.skip_nodes:
        report.results.append(check_nodes(v1))

    report.results.append(check_system_pods(v1))

    if not args.skip_argo:
        report.results.append(check_argo_apps(custom_api, config_apps))

    report.results.append(check_app_pods(v1, config_apps))
    report.results.append(check_app_configs(config_apps))

    # Output
    if args.json_output:
        print_json(report)
    else:
        print_report(report)

    return 1 if report.overall == Status.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
