#!/usr/bin/env python3
"""
deploy-mikrotik.py — ad-hoc .rsc deployer for Mikrotik devices.

Use this when you want to push a single .rsc to one or more devices
without running the full Ansible playbook. Useful for testing changes
in isolation, or for one-off fixes.

Usage:
  ./deploy-mikrotik.py --device 10.49.48.1 --rsc mikrotik/rb5009/vlan10-add.rsc
  ./deploy-mikrotik.py --inventory mikrotik/hosts.txt --rsc-all
  ./deploy-mikrotik.py --device 10.49.48.1 --rsc file.rsc --dry-run

Reads SSH config from the env or CLI flags: SSH_USER, SSH_KEY, SSH_PORT.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import paramiko  # type: ignore[import-untyped]


def deploy(
    host: str,
    user: str,
    key_path: str,
    port: int,
    local_files: list[Path],
    dry_run: bool,
) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"==> {host}: connecting ssh://{user}@{host}:{port}")
    try:
        client.connect(host, port=port, username=user, key_filename=key_path, timeout=15)
    except Exception as e:
        print(f"FAIL: {e}")
        return
    sftp = client.open_sftp()

    for local in local_files:
        remote = f"/{local.name}"
        print(f"  -> {host}: scp {local} -> {remote}")
        if not dry_run:
            sftp.put(str(local), remote)
        print(f"  -> {host}: /import file={local.name}")
        if not dry_run:
            stdin_, stdout, stderr = client.exec_command(
                f"/import file={local.name}", timeout=30
            )
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            if out:
                print(f"     stdout: {out}")
            if err:
                print(f"     stderr: {err}")

    if not dry_run:
        # Clean up the uploaded files
        for local in local_files:
            cmd = f'/file remove [find name={local.name}]'
            client.exec_command(cmd)

    sftp.close()
    client.close()
    print(f"==> {host}: done")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--device", action="append", help="device IP (repeatable)")
    ap.add_argument(
        "--inventory",
        type=Path,
        help="file with one device per line (# comments ok)",
    )
    ap.add_argument("--user", default=os.environ.get("SSH_USER", "raypappa"))
    ap.add_argument(
        "--key",
        default=os.environ.get("SSH_KEY", os.path.expanduser("~/.ssh/raypappa")),
    )
    ap.add_argument(
        "--port", type=int, default=int(os.environ.get("SSH_PORT", "2200"))
    )
    ap.add_argument("--rsc", action="append", type=Path, help=".rsc file to deploy")
    ap.add_argument(
        "--rsc-all",
        action="store_true",
        help="deploy every .rsc in the role's files/<host>/ (when used with --device <host>)",
    )
    ap.add_argument("--dry-run", action="store_true", help="print what would happen")
    args = ap.parse_args()

    if not args.rsc and not args.rsc_all:
        ap.error("at least one --rsc is required, or pass --rsc-all")

    devices: list[str] = []
    if args.device:
        devices.extend(args.device)
    if args.inventory:
        for line in args.inventory.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            devices.append(line)

    if not devices:
        ap.error("at least one --device or --inventory is required")

    if args.rsc_all:
        # Re-derive the rsc files per host
        # The convention is mikrotik/<hostname>/*.rsc
        # When using --device <ip>, --rsc-all has no per-host logic; use
        # --rsc explicitly in that case.
        ap.error(
            "--rsc-all currently expects --inventory with hostnames matching "
            "the mikrotik/<name> directory layout"
        )

    rc = 0
    for host in devices:
        try:
            deploy(host, args.user, args.key, args.port, args.rsc or [], args.dry_run)
        except Exception as e:
            print(f"FAIL on {host}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
