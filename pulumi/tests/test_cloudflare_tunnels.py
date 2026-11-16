import unittest

from stacks.cloudflare_tunnels import (
    REMOTE_TUNNELS,
    tunnel_identifiers,
    validate_tunnel_config,
)


class CloudflareTunnelConfigTests(unittest.TestCase):
    def test_tunnel_identifiers_use_tunnel_specific_config(self):
        config = {
            "accountId": "account-id",
            "argocd": {"tunnelId": "tunnel-id"},
        }

        self.assertEqual(
            tunnel_identifiers("argocd", config),
            ("account-id", "tunnel-id"),
        )

    def test_argocd_ingress_uses_verified_https_origin(self):
        argocd = REMOTE_TUNNELS["argocd"]
        config = argocd["config"]
        route, catch_all = config["ingresses"]

        self.assertEqual(route["hostname"], "argocd.fieldsofbears.com")
        self.assertEqual(
            route["service"],
            "https://argocd-server.argocd.svc.cluster.local:443",
        )
        self.assertEqual(
            route["origin_request"]["origin_server_name"],
            "argocd.internal.stoneydavis.com",
        )
        self.assertFalse(route["origin_request"]["no_tls_verify"])
        self.assertEqual(catch_all, {"service": "http_status:404"})
        self.assertEqual(
            argocd["observed_unsupported_config"],
            {"warp-routing": {"enabled": False}},
        )
        validate_tunnel_config("argocd", config)

    def test_tunnel_config_allows_top_level_origin_request_and_path_route(self):
        config = {
            "origin_request": {"origin_server_name": "origin.example.com"},
            "ingresses": [
                {"path": "/api/*", "service": "http://origin:80"},
                {"service": "http_status:404"},
            ],
        }

        validate_tunnel_config("example", config)
        self.assertEqual(
            config["origin_request"]["origin_server_name"],
            "origin.example.com",
        )

    def test_tunnel_config_requires_http_404_catch_all(self):
        with self.assertRaisesRegex(ValueError, "http_status:404"):
            validate_tunnel_config(
                "example",
                {
                    "ingresses": [
                        {"hostname": "example.com", "service": "http://origin:80"},
                        {"service": "http_status:403"},
                    ]
                },
            )

    def test_tunnel_config_requires_final_catch_all(self):
        with self.assertRaisesRegex(ValueError, "catch-all"):
            validate_tunnel_config(
                "example",
                {
                    "ingresses": [
                        {"hostname": "example.com", "service": "http://origin:80"}
                    ]
                },
            )


if __name__ == "__main__":
    unittest.main()
