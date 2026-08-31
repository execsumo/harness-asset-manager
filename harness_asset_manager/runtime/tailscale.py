from __future__ import annotations

import json
import shutil
import subprocess


def detect_tailnet_dns_name(*, timeout: float = 2.0) -> str | None:
    """Best-effort local Tailscale hostname, or ``None`` if unavailable.

    Reads the same ``tailscale status --json`` field ``scripts/serve-tailnet.sh``
    already relies on. Never raises: a missing CLI, a stopped daemon, a timeout, or
    unexpected output all resolve to "not detected" rather than blocking startup —
    this only ever *widens* the Host/Origin allowlist, it does not weaken it, so a
    detection failure should fail toward "unchanged", not toward an error.
    """
    executable = shutil.which("tailscale")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "status", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    dns_name = payload.get("Self", {}).get("DNSName", "")
    if not isinstance(dns_name, str):
        return None
    dns_name = dns_name.rstrip(".").strip()
    return dns_name or None
