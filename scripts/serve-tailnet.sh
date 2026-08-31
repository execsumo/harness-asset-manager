#!/usr/bin/env bash
# Point the tailnet front door at the local app.
#
# `tailscale serve --bg` writes into tailscaled's own state, which survives reboots,
# so this is a re-apply path (after a tailscaled state loss, or to move the port),
# not something that has to run on every boot.
#
#   HAM_TAILNET_PORT=7443  the HTTPS port the app is published on over the tailnet
#   HAM_BACKEND_PORT=8000  the loopback port the app itself listens on
set -euo pipefail

PORT="${HAM_TAILNET_PORT:-7443}"
BACKEND="${HAM_BACKEND_PORT:-8000}"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "error: tailscale CLI not found in PATH." >&2
  exit 1
fi

TS_STATUS="$(tailscale status --json 2>/dev/null || true)"
if [ -z "${TS_STATUS}" ]; then
  echo "error: failed to read tailscale status — is Tailscale running?" >&2
  exit 1
fi

DNS_NAME="$(python3 -c '
import json, sys
data = json.loads(sys.argv[1])
dns = data.get("Self", {}).get("DNSName", "").rstrip(".")
print(dns)
' "${TS_STATUS}")"

if [ -z "${DNS_NAME}" ]; then
  echo "error: could not determine Tailscale DNS name from tailscale status." >&2
  exit 1
fi

echo "Tailnet DNS name: ${DNS_NAME}"

if ! curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:${BACKEND}/api/health"; then
  echo "error: nothing answering on http://127.0.0.1:${BACKEND}/ — start the app first." >&2
  echo "Start command: harnessam start --trusted-host ${DNS_NAME}" >&2
  exit 1
fi

# Verify the app accepts the proxied Host header (running with --trusted-host)
if ! curl -fsS --max-time 5 -o /dev/null -H "Host: ${DNS_NAME}" "http://127.0.0.1:${BACKEND}/api/health"; then
  echo "warning: app at 127.0.0.1:${BACKEND} rejected Host: ${DNS_NAME} (HTTP 403)." >&2
  echo "Make sure the app is running WITHOUT --allow-remote and WITH --trusted-host ${DNS_NAME}" >&2
fi

tailscale serve --bg --https="${PORT}" "http://127.0.0.1:${BACKEND}"

# Other ports may still proxy the same backend (e.g. a port this replaces). Report
# them rather than deleting them — this host runs unrelated apps behind other ports.
stale="$(tailscale serve status --json \
  | python3 -c '
import json, sys
cfg = json.load(sys.stdin)
port, backend = sys.argv[1], sys.argv[2]
for host, entry in (cfg.get("Web") or {}).items():
    listen = host.rsplit(":", 1)[-1]
    if listen == port:
        continue
    for handler in (entry.get("Handlers") or {}).values():
        if handler.get("Proxy", "").endswith(f":{backend}"):
            print(listen)
' "${PORT}" "${BACKEND}")"

if [ -n "${stale}" ]; then
  echo
  echo "note: these ports also proxy 127.0.0.1:${BACKEND}. Turn off any you no longer want:"
  for old in ${stale}; do
    echo "  tailscale serve --https=${old} off"
  done
fi

echo
tailscale serve status
