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

if ! curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:${BACKEND}/"; then
  echo "error: nothing answering on http://127.0.0.1:${BACKEND}/ — start the app first." >&2
  exit 1
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
