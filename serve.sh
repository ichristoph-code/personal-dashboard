#!/bin/bash
# Dashboard server — thin wrapper around dashboard.py --serve.
# Launched at login by the LaunchAgent, or run manually in Terminal.
# Ctrl+C to stop.

DIR="/Users/ianchristoph/Code"

cd "$DIR" || exit 1

# dashboard.py --serve generates the HTML, starts the HTTP server with
# /refresh endpoint, Claude chat API, config save, and auto-refresh.
exec /usr/bin/python3 "$DIR/dashboard.py" --serve
