#!/bin/bash
# Dashboard HTTP server — started at login by LaunchAgent

DIR="/Users/ianchristoph/Code"
PORT=8080

exec /usr/bin/python3 - << 'PYEOF'
import http.server, socketserver, subprocess, threading

DIR = "/Users/ianchristoph/Code"
PORT = 8080

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIR, **k)
    def do_GET(self):
        if self.path.startswith('/refresh'):
            def run():
                subprocess.run(
                    ['/bin/bash', '-l', '-c',
                     'cd "/Users/ianchristoph/Code" && /usr/bin/python3 "/Users/ianchristoph/Code/dashboard.py"'],
                    cwd=DIR
                )
            threading.Thread(target=run, daemon=True).start()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'ok')
        else:
            super().do_GET()
    def log_message(self, *a):
        pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', PORT), H) as s:
    print(f'Dashboard server running on http://localhost:{PORT}', flush=True)
    s.serve_forever()
PYEOF
