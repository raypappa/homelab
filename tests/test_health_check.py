from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

from kubernetes.client.rest import ApiException

from scripts import health_check


class HealthCheckDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.terminated = SimpleNamespace(
            reason="Error",
            exit_code=1,
            message="backup command failed",
        )
        self.container_status = SimpleNamespace(
            name="restic",
            ready=False,
            restart_count=1,
            state=SimpleNamespace(
                waiting=SimpleNamespace(
                    reason="CrashLoopBackOff",
                    message="retrying after failure",
                ),
                terminated=None,
            ),
            last_state=SimpleNamespace(terminated=self.terminated),
        )
        self.pod = SimpleNamespace(
            metadata=SimpleNamespace(
                name="backup-pod",
                owner_references=[SimpleNamespace(kind="Job", name="backup")],
            ),
            status=SimpleNamespace(
                phase="Failed",
                reason="BackoffLimitExceeded",
                message="Job has reached the specified backoff limit",
                conditions=[
                    SimpleNamespace(
                        type="Ready",
                        status="False",
                        reason="ContainersNotReady",
                        message="containers with unready status: [restic]",
                    )
                ],
                init_container_statuses=[],
                container_statuses=[self.container_status],
            ),
        )

    def test_failed_pod_reports_state_and_redacted_previous_logs(self) -> None:
        api = Mock()
        api.read_namespaced_pod_log.return_value = repr(
            b"backup failed: password=hunter2\n"
            b"\x1b[2KAuthorization: Bearer abcdefghijklmnopqrstuvwxyz"
        )

        details = health_check._pod_diagnostic_details(
            cast(Any, api), "jellyfin", cast(Any, self.pod), health_check.LogBudget()
        )
        report = "\n".join(details)

        self.assertIn("phase=Failed owner=Job/backup", report)
        self.assertIn("BackoffLimitExceeded", report)
        self.assertIn("CrashLoopBackOff", report)
        self.assertIn("exitCode=1", report)
        self.assertIn("recent logs (previous container)", report)
        self.assertIn("password=[REDACTED]", report)
        self.assertNotIn("hunter2", report)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", report)
        self.assertNotIn("\x1b", report)
        api.read_namespaced_pod_log.assert_called_once_with(
            name="backup-pod",
            namespace="jellyfin",
            container="restic",
            previous=True,
            tail_lines=health_check.MAX_LOG_LINES,
        )

    def test_forbidden_log_access_is_reported_without_raising(self) -> None:
        api = Mock()
        api.read_namespaced_pod_log.side_effect = ApiException(
            status=403,
            reason="Forbidden",
        )

        details = health_check._pod_diagnostic_details(
            cast(Any, api), "jellyfin", cast(Any, self.pod), health_check.LogBudget()
        )

        self.assertTrue(
            any("logs unavailable (HTTP 403 Forbidden)" in item for item in details)
        )

    def test_log_budget_limits_pod_log_requests(self) -> None:
        api = Mock()
        budget = health_check.LogBudget(remaining=0)

        details = health_check._pod_diagnostic_details(
            cast(Any, api), "jellyfin", cast(Any, self.pod), budget
        )

        self.assertIn("log excerpts omitted after 20 requests", details)
        api.read_namespaced_pod_log.assert_not_called()

    def test_argo_out_of_sync_includes_condition_and_resource(self) -> None:
        api = Mock()
        api.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "jellyfin"},
                    "status": {
                        "sync": {"status": "OutOfSync"},
                        "health": {"status": "Healthy"},
                        "conditions": [
                            {
                                "type": "ComparisonError",
                                "message": "invalid config token=secret",
                            }
                        ],
                        "resources": [
                            {
                                "kind": "Deployment",
                                "namespace": "jellyfin",
                                "name": "jellyfin",
                                "status": "OutOfSync",
                                "health": {"status": "Healthy"},
                            },
                            {
                                "kind": "Service",
                                "namespace": "jellyfin",
                                "name": "healthy",
                                "status": "Synced",
                                "health": {"status": "Unknown"},
                            },
                        ],
                    },
                }
            ]
        }

        result = health_check.check_argo_apps(cast(Any, api), {})
        report = "\n".join(result.details)

        self.assertEqual(result.status, health_check.Status.FAIL)
        self.assertIn("condition ComparisonError", report)
        self.assertIn("Deployment/jellyfin/jellyfin: sync=OutOfSync", report)
        self.assertNotIn("Service/jellyfin/healthy", report)
        self.assertIn("token=[REDACTED]", report)
        self.assertNotIn("secret", report)

    def test_healthy_pod_does_not_fetch_logs(self) -> None:
        api = Mock()
        api.list_namespaced_pod.return_value = SimpleNamespace(
            items=[
                SimpleNamespace(
                    metadata=SimpleNamespace(
                        name="jellyfin-0",
                        owner_references=[],
                    ),
                    status=SimpleNamespace(
                        phase="Running",
                        conditions=[SimpleNamespace(type="Ready", status="True")],
                        container_statuses=[
                            SimpleNamespace(
                                name="jellyfin",
                                ready=True,
                                restart_count=0,
                                state=SimpleNamespace(
                                    running=object(),
                                    waiting=None,
                                    terminated=None,
                                ),
                                last_state=None,
                            )
                        ],
                        init_container_statuses=[],
                    ),
                )
            ]
        )

        result = health_check.check_app_pods(
            cast(Any, api), {"jellyfin": {"destNamespace": "jellyfin"}}
        )

        self.assertEqual(result.status, health_check.Status.OK)
        api.read_namespaced_pod_log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
