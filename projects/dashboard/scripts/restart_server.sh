#!/bin/bash
# restart_server.sh — Kill, regenerate, and restart the dashboard server.
# Usage: ./scripts/restart_server.sh [port]
#
# This script ensures the running server always has the latest code:
#   1. Kills any existing server on the port
#   2. Regenerates dashboard.html from current source
#   3. Starts the server with --serve
#   4. Waits until it's ready and verifies endpoints

PORT="${1:-8080}"
DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Stopping any server on port $PORT..."
lsof -ti :"$PORT" | xargs kill 2>/dev/null
sleep 1

echo "==> Regenerating dashboard.html..."
cd "$DIR" && python3 dashboard.py 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Dashboard generation failed!"
    exit 1
fi

echo "==> Starting server on port $PORT..."
cd "$DIR" && python3 dashboard.py --serve --port "$PORT" &>/dev/null &
SERVER_PID=$!

# Wait for server to be ready (up to 30 seconds)
echo -n "==> Waiting for server"
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w '' http://localhost:"$PORT"/dashboard.html 2>/dev/null; then
        echo " ready!"
        echo "==> Server PID: $SERVER_PID, port: $PORT"
        echo "==> Dashboard: http://localhost:$PORT/dashboard.html"
        exit 0
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "WARNING: Server may still be starting (data fetch can take 30-60s)."
echo "PID $SERVER_PID is running — check with: lsof -i :$PORT"
