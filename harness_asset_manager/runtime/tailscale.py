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


def apply_tailnet_serve(*, https_port: int, backend_port: int, timeout: float = 5.0) -> bool:
    """Best-effort ``tailscale serve --bg`` mapping from ``https_port`` to this backend.

    Same call ``scripts/serve-tailnet.sh`` makes by hand: publishes this app at
    ``https://<this device's tailnet name>:<https_port>``, written into tailscaled's own
    persistent state. Never raises — a missing CLI, a stopped daemon, a timeout, or a
    non-zero exit all resolve to "not applied" rather than blocking startup.
    """
    executable = shutil.which("tailscale")
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable, "serve", "--bg", f"--https={https_port}", f"http://127.0.0.1:{backend_port}"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def disable_tailnet_serve(*, https_port: int, timeout: float = 5.0) -> bool:
    """Best-effort teardown of the single port ``apply_tailnet_serve`` mapped.

    Scoped to exactly one port via ``--https=<port> off`` — never ``serve reset``, which
    would also drop any unrelated apps this host proxies on other ports. Never raises.
    """
    executable = shutil.which("tailscale")
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable, "serve", f"--https={https_port}", "off"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
