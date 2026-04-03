#!/bin/bash
# Refresh the Personal Dashboard
cd "$(dirname "$0")/.."
python3 dashboard.py
# Reopen the dashboard in the default browser
open dashboard.html
