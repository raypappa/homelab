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
import ast
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from kubernetes.client.rest import ApiException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from kubernetes import client, config

if TYPE_CHECKING:
    from kubernetes.client.models.v1_node import V1Node
    from kubernetes.client.models.v1_node_condition import V1NodeCondition
    from kubernetes.client.models.v1_pod import V1Pod

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARGOCD_NAMESPACE = "argocd"
SYSTEM_NAMESPACE = "kube-system"
APPS_DIR = pathlib.Path("kubernetes/main/apps")
MAX_LOG_LINES = 20
MAX_LOG_CHARS = 800
MAX_LOG_REQUESTS = 20
MAX_DIAGNOSTIC_CHARS = 400
MAX_ARGO_RESOURCE_DETAILS = 10

_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)([\"']?(?:[a-z0-9_.-]*(?:password|passwd|token|secret|api[_-]?key|credential)[a-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;}]+)"
)
_AUTH_HEADER_RE = re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s,;]+")
_BEARER_TOKEN_RE = re.compile(r"(?i)(\bbearer\s+)[a-z0-9._~+/-]{8,}={0,2}")
_URL_CREDENTIALS_RE = re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

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
class LogBudget:
    remaining: int = MAX_LOG_REQUESTS
    limit_reported: bool = False


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


UNHEALTHY_CONTAINER_REASONS = frozenset(
    {
        "CrashLoopBackOff",
        "ImagePullBackOff",
        "ErrImagePull",
        "InvalidImageName",
        "CreateContainerConfigError",
        "CreateContainerError",
        "RunContainerError",
        "PreStartHookError",
        "ExceededGracePeriod",
    }
)


def _container_has_issues(pod: V1Pod) -> list[str]:
    """Return list of container status strings for unhealthy containers."""
    issues: list[str] = []
    if not pod.status:
        return issues
    for c in pod.status.container_statuses or []:
        if (
            c.state
            and c.state.waiting
            and c.state.waiting.reason in UNHEALTHY_CONTAINER_REASONS
        ):
            issues.append(f"{c.name}: {c.state.waiting.reason}")
        if c.state and c.state.terminated and c.state.terminated.exit_code != 0:
            issues.append(
                f"{c.name}: {c.state.terminated.reason or 'exit code ' + str(c.state.terminated.exit_code)}"
            )
    for c in pod.status.init_container_statuses or []:
        if (
            c.state
            and c.state.waiting
            and c.state.waiting.reason in UNHEALTHY_CONTAINER_REASONS
        ):
            issues.append(f"{c.name}: {c.state.waiting.reason}")
    return issues


def _safe_diagnostic(value: Any, limit: int = MAX_DIAGNOSTIC_CHARS) -> str:
    """Bound diagnostic text and redact common credential formats."""
    text = str(value).strip()
    text = _ANSI_ESCAPE_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = _SENSITIVE_VALUE_RE.sub(r"\1[REDACTED]", text)
    text = _AUTH_HEADER_RE.sub(r"\1[REDACTED]", text)
    text = _BEARER_TOKEN_RE.sub(r"\1[REDACTED]", text)
    text = _URL_CREDENTIALS_RE.sub(r"\1[REDACTED]@", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _decode_log_text(value: Any) -> str:
    """Decode Kubernetes client log responses, including its bytes repr form."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    text = str(value)
    if text.startswith(("b'", 'b"')):
        try:
            decoded = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return text
        if isinstance(decoded, bytes):
            return decoded.decode("utf-8", errors="replace")
    return text


def _container_needs_diagnostics(
    container_status: Any,
    role: str,
) -> bool:
    """Return whether this container's state warrants details and a log tail."""
    state = container_status.state
    last_state = container_status.last_state
    waiting = state.waiting if state else None
    terminated = state.terminated if state else None
    last_terminated = last_state.terminated if last_state else None
    completed_init = bool(role == "init" and terminated and terminated.exit_code == 0)
    return bool(
        (container_status.ready is False and not completed_init)
        or (waiting and waiting.reason in UNHEALTHY_CONTAINER_REASONS)
        or (terminated and terminated.exit_code != 0)
        or (last_terminated and last_terminated.exit_code != 0)
    )


def _container_diagnostic(container_status: Any, role: str) -> str:
    """Format status details for a container that needs investigation."""
    parts: list[str] = []
    if container_status.ready is False:
        parts.append("not-ready")

    state = container_status.state
    last_state = container_status.last_state
    waiting = state.waiting if state else None
    terminated = state.terminated if state else None
    last_terminated = last_state.terminated if last_state else None

    message = ""
    if waiting:
        parts.append(f"waiting={waiting.reason or 'Unknown'}")
        message = waiting.message or ""
    if terminated and (terminated.exit_code != 0 or role == "init"):
        parts.append(
            f"terminated={terminated.reason or 'Unknown'} exitCode={terminated.exit_code}"
        )
        message = terminated.message or message
    if last_terminated and last_terminated.exit_code != 0:
        parts.append(
            f"lastTerminated={last_terminated.reason or 'Unknown'} "
            f"exitCode={last_terminated.exit_code}"
        )
        message = last_terminated.message or message
    if not parts:
        parts.append("state=unknown")

    restart_count = container_status.restart_count or 0
    detail = (
        f"{role} container {container_status.name}: "
        f"{', '.join(parts)}, restarts={restart_count}"
    )
    if message:
        detail += f"; message={_safe_diagnostic(message)}"
    return detail


def _container_log_details(
    v1: client.CoreV1Api,
    namespace: str,
    pod_name: str,
    container_statuses: list[Any],
    budget: LogBudget,
    role: str,
) -> list[str]:
    """Fetch bounded recent logs only for containers with failure signals."""
    details: list[str] = []
    for container_status in container_statuses:
        if not _container_needs_diagnostics(container_status, role):
            continue
        if budget.remaining <= 0:
            if not budget.limit_reported:
                details.append(
                    f"log excerpts omitted after {MAX_LOG_REQUESTS} requests"
                )
                budget.limit_reported = True
            break

        last_state = container_status.last_state
        previous = bool(
            (container_status.restart_count or 0) > 0
            and last_state
            and last_state.terminated
        )
        budget.remaining -= 1
        suffix = " (previous container)" if previous else ""
        try:
            log_text = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_status.name,
                previous=previous,
                tail_lines=MAX_LOG_LINES,
            )
        except ApiException as exc:
            status = f"HTTP {exc.status}" if exc.status else "API error"
            reason = f" {exc.reason}" if exc.reason else ""
            details.append(
                f"{container_status.name}: logs unavailable ({status}{reason})"
            )
            continue
        except (Urllib3HTTPError, OSError) as exc:
            details.append(
                f"{container_status.name}: log fetch error ({type(exc).__name__})"
            )
            continue

        log_value = _decode_log_text(log_text)
        lines = [line.strip() for line in log_value.splitlines() if line.strip()]
        if not lines:
            details.append(f"{container_status.name}: no log output{suffix}")
            continue
        excerpt = _safe_diagnostic(
            " | ".join(lines[-MAX_LOG_LINES:]),
            limit=MAX_LOG_CHARS,
        )
        details.append(f"{container_status.name}: recent logs{suffix}: {excerpt}")
    return details


def _pod_diagnostic_details(
    v1: client.CoreV1Api,
    namespace: str,
    pod: V1Pod,
    budget: LogBudget,
) -> list[str]:
    """Describe a failed pod and fetch concise logs from affected containers."""
    meta = pod.metadata
    status = pod.status
    pod_name = meta.name if meta and meta.name else "<unknown>"
    phase = status.phase if status and status.phase else "Unknown"
    owners = meta.owner_references if meta and meta.owner_references else []
    owner = f" owner={owners[0].kind}/{owners[0].name}" if owners else ""
    summary = f"{namespace}/{pod_name}: phase={phase}{owner}"
    details = [summary]

    if status and status.reason:
        details.append(f"{pod_name}: reason={status.reason}")
    if status and status.message:
        details.append(f"{pod_name}: message={_safe_diagnostic(status.message)}")

    conditions = status.conditions if status and status.conditions else []
    ready_condition = next(
        (condition for condition in conditions if condition.type == "Ready"), None
    )
    if ready_condition and ready_condition.status != "True":
        condition_text = f"Ready={ready_condition.status}"
        if ready_condition.reason:
            condition_text += f" reason={ready_condition.reason}"
        if ready_condition.message:
            condition_text += f"; {_safe_diagnostic(ready_condition.message)}"
        details.append(f"{pod_name}: {condition_text}")

    container_groups = (
        ("init", status.init_container_statuses if status else None),
        ("app", status.container_statuses if status else None),
    )
    for role, container_statuses in container_groups:
        if not container_statuses:
            continue
        for container_status in container_statuses:
            if _container_needs_diagnostics(container_status, role):
                details.append(_container_diagnostic(container_status, role))
        details.extend(
            _container_log_details(
                v1,
                namespace,
                pod_name,
                container_statuses,
                budget,
                role,
            )
        )
    return details


def _argo_diagnostic_details(status: dict[str, Any]) -> list[str]:
    """Summarize Argo conditions and resources needing sync or health attention."""
    details: list[str] = []
    for condition in status.get("conditions") or []:
        condition_type = condition.get("type", "Unknown")
        message = condition.get("message", "")
        text = f"condition {condition_type}"
        if message:
            text += f": {_safe_diagnostic(message)}"
        details.append(text)

    resources = status.get("resources") or []
    affected_resources = [
        resource
        for resource in resources
        if resource.get("status", "Unknown") != "Synced"
        or (resource.get("health") or {}).get("status", "Unknown")
        not in ("Healthy", "Unknown")
    ]
    for resource in affected_resources[:MAX_ARGO_RESOURCE_DETAILS]:
        identity = "/".join(
            part
            for part in (
                resource.get("kind", "Resource"),
                resource.get("namespace", ""),
                resource.get("name", "<unknown>"),
            )
            if part
        )
        health_status = (resource.get("health") or {}).get("status", "Unknown")
        details.append(
            f"resource {identity}: sync={resource.get('status', 'Unknown')}, "
            f"health={health_status}"
        )
    omitted = len(affected_resources) - MAX_ARGO_RESOURCE_DETAILS
    if omitted > 0:
        details.append(f"{omitted} additional affected resource(s) omitted")
    if not details:
        details.append("Argo CD reported no condition or resource-level details")
    return details


def check_system_pods(
    v1: client.CoreV1Api,
    log_budget: LogBudget | None = None,
) -> CheckResult:
    """Check that kube-system pods are running and ready."""
    result = CheckResult(name="System Pods", status=Status.OK)
    try:
        pods: list[V1Pod] = v1.list_namespaced_pod(
            namespace=SYSTEM_NAMESPACE,
        ).items
    except ApiException as exc:
        result.status = Status.FAIL
        result.details.append(f"API error: {exc.reason}")
        return result

    budget = log_budget or LogBudget()
    unhealthy = False
    for pod in pods:
        status = pod.status
        phase = status.phase if status and status.phase else "Unknown"
        if phase == "Succeeded":
            continue
        conditions = status.conditions if status and status.conditions else []
        ready_condition = next(
            (condition for condition in conditions if condition.type == "Ready"),
            None,
        )
        if (
            phase != "Running"
            or (ready_condition and ready_condition.status != "True")
            or _container_has_issues(pod)
        ):
            unhealthy = True
            result.status = Status.FAIL
            result.details.extend(
                _pod_diagnostic_details(v1, SYSTEM_NAMESPACE, pod, budget)
            )

    if not unhealthy:
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
            result.details.extend(
                f"{name}: {detail}" for detail in _argo_diagnostic_details(status)
            )

    if not result.details:
        result.details.append(f"{len(managed_items)} app(s) synced and healthy")
    return result


def check_app_pods(
    v1: client.CoreV1Api,
    config_apps: dict[str, dict[str, Any]],
    log_budget: LogBudget | None = None,
) -> CheckResult:
    """Check pod readiness for each managed application namespace."""
    result = CheckResult(name="App Pods", status=Status.OK)

    # Collect unique namespaces from config (exclude system namespaces)
    namespaces = {
        app.get("destNamespace")
        for app in config_apps.values()
        if app.get("destNamespace") not in (SYSTEM_NAMESPACE, ARGOCD_NAMESPACE, None)
    }

    budget = log_budget or LogBudget()
    for ns in sorted(ns for ns in namespaces if ns is not None):
        try:
            pods: list[V1Pod] = v1.list_namespaced_pod(
                namespace=ns,
                field_selector="status.phase!=Succeeded",
            ).items
        except ApiException as exc:
            result.status = Status.WARN
            result.details.append(f"{ns}: API error ({exc.reason})")
            continue

        unhealthy_pods: list[V1Pod] = []
        for pod in pods:
            pod_status = pod.status
            phase = pod_status.phase if pod_status and pod_status.phase else "Unknown"
            conditions = (
                pod_status.conditions if pod_status and pod_status.conditions else []
            )
            ready_cond = next((c for c in conditions if c.type == "Ready"), None)
            if (
                phase != "Running"
                or (ready_cond and ready_cond.status != "True")
                or _container_has_issues(pod)
            ):
                unhealthy_pods.append(pod)

        if unhealthy_pods:
            result.status = Status.FAIL
            result.details.append(f"{ns}: {len(unhealthy_pods)} unhealthy pod(s)")
            for pod in unhealthy_pods:
                result.details.extend(_pod_diagnostic_details(v1, ns, pod, budget))

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
    log_budget = LogBudget()

    if not args.skip_nodes:
        report.results.append(check_nodes(v1))

    report.results.append(check_system_pods(v1, log_budget))

    if not args.skip_argo:
        report.results.append(check_argo_apps(custom_api, config_apps))

    report.results.append(check_app_pods(v1, config_apps, log_budget))
    report.results.append(check_app_configs(config_apps))

    # Output
    if args.json_output:
        print_json(report)
    else:
        print_report(report)

    return 1 if report.overall == Status.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
