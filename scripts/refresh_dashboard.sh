#!/bin/bash
# Dashboard Refresh Script
# Called by LaunchAgent com.ian.dashboard-refresh every 30 minutes.
# Wraps dashboard.py with logging, error handling, and proper environment.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="/tmp/dashboard-refresh.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "=== Dashboard refresh started at $TIMESTAMP ===" >> "$LOG_FILE"

cd "$PROJECT_DIR" || {
    echo "[$TIMESTAMP] ERROR: Could not cd to $PROJECT_DIR" >> "$LOG_FILE"
    exit 1
}

# Run dashboard.py and capture output/errors
/usr/bin/python3 "$PROJECT_DIR/dashboard.py" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

TIMESTAMP_END=$(date '+%Y-%m-%d %H:%M:%S')
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP_END] Dashboard refreshed successfully." >> "$LOG_FILE"
else
    echo "[$TIMESTAMP_END] ERROR: dashboard.py exited with code $EXIT_CODE" >> "$LOG_FILE"
fi

# Keep log file from growing too large (last 200 lines)
if [ -f "$LOG_FILE" ]; then
    tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

exit $EXIT_CODE
