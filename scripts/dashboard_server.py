#!/usr/bin/env python3
"""
Dashboard HTTP server.
Serves static files from the project directory and handles /refresh
to regenerate dashboard.html on demand.
Starts automatically at login via LaunchAgent.
"""
import http.server
import socketserver
import subprocess
import threading
import sys
import os

DIR = "/Users/ianchristoph/Code"
PORT = 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIR, **kw)

    def do_GET(self):
        if self.path == "/refresh" or self.path.startswith("/refresh?"):
            threading.Thread(target=self._run_dashboard, daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            super().do_GET()

    def _run_dashboard(self):
        script = os.path.join(DIR, "dashboard.py")
        subprocess.run(
            ["/bin/bash", "-l", "-c", f"cd '{DIR}' && /usr/bin/python3 '{script}'"],
            cwd=DIR,
        )

    def log_message(self, fmt, *args):
        pass  # suppress per-request logs


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Dashboard server running on http://localhost:{PORT}/dashboard.html", flush=True)
    httpd.serve_forever()
