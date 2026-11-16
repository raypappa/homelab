"""Pulumi configuration for remotely managed Cloudflare Tunnels.

Only tunnels with ``config_src="cloudflare"`` belong here. Tunnels using
local ``cloudflared`` configuration remain managed by their Kubernetes app.
"""

import pulumi_cloudflare as cloudflare

import pulumi

# Add tunnels incrementally after reviewing their complete live API config.
# The provider config below can also include top-level ``origin_request``.
# Cloudflare v6.24.0 does not model the API's ``warp-routing`` field. The
# current Argo tunnel has it disabled; do not add tunnels that enable it until
# the provider can represent that setting.
REMOTE_TUNNELS = {
    "argocd": {
        "config": {
            "ingresses": [
                {
                    "hostname": "argocd.fieldsofbears.com",
                    "service": "https://argocd-server.argocd.svc.cluster.local:443",
                    "origin_request": {
                        "origin_server_name": "argocd.internal.stoneydavis.com",
                        "no_tls_verify": False,
                    },
                },
                {"service": "http_status:404"},
            ],
        },
        "observed_unsupported_config": {"warp-routing": {"enabled": False}},
    },
}


def validate_tunnel_config(tunnel_name: str, config: dict) -> None:
    """Reject incomplete tunnel configs before registering them with Pulumi."""
    ingresses = config.get("ingresses")
    if not isinstance(ingresses, list) or not ingresses:
        raise ValueError(f"Tunnel {tunnel_name!r} must have ingress rules")

    for ingress in ingresses[:-1]:
        if (
            not isinstance(ingress, dict)
            or not ingress.get("service")
            or not (ingress.get("hostname") or ingress.get("path"))
        ):
            raise ValueError(
                f"Tunnel {tunnel_name!r} has a non-catch-all rule without "
                "a hostname or path and service"
            )

    if ingresses[-1] != {"service": "http_status:404"}:
        raise ValueError(
            f"Tunnel {tunnel_name!r} must end with an http_status:404 catch-all"
        )


def tunnel_identifiers(tunnel_name: str, config: dict) -> tuple[str, str]:
    """Read the account and tunnel IDs from the tunnel-specific config object."""
    account_id = config["accountId"]
    tunnel_id = config[tunnel_name]["tunnelId"]
    return account_id, tunnel_id


def register_cloudflare_tunnel_configs() -> None:
    """Adopt and manage the declared Cloudflare dashboard tunnel configs."""
    config = pulumi.Config()
    tunnel_configs = config.require_object("cloudflare_tunnels")

    for name, tunnel in REMOTE_TUNNELS.items():
        account_id, tunnel_id = tunnel_identifiers(name, tunnel_configs)
        tunnel_config = tunnel["config"]
        validate_tunnel_config(name, tunnel_config)

        cloudflare.ZeroTrustTunnelCloudflaredConfig(
            f"{name}-cloudflare-tunnel-config",
            account_id=account_id,
            tunnel_id=tunnel_id,
            source="cloudflare",
            config=tunnel_config,
            opts=pulumi.ResourceOptions(import_=f"{account_id}/{tunnel_id}"),
        )
