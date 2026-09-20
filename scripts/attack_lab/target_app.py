"""
NetWatch Attack Lab — Mock Enterprise Web Server.

Target application deployed on the virtual network (10.0.0.2:8080 / 0.0.0.0:8080).
Provides realistic web endpoints, authentication forms, mock APIs, and metrics
to receive and log simulated attack traffic.

Includes standard-library fallback for zero-dependency portability.
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [TargetApp] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("target_app")

START_TIME = time.time()
STATS = {
    "total_requests": 0,
    "get_requests": 0,
    "post_requests": 0,
    "login_attempts": 0,
    "login_failures": 0,
    "login_successes": 0,
    "unique_ips": set(),
    "last_request_time": None,
    "last_client_ip": None,
    "requests_by_path": {},
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Portal — Attack Lab Target</title>
    <style>
        :root {
            --bg: #0b0f19;
            --card-bg: #131b2e;
            --border: #243452;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --danger: #ef4444;
            --success: #10b981;
            --text: #f1f5f9;
            --text-dim: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px; }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 32px; width: 100%; max-width: 440px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .badge { display: inline-flex; align-items: center; gap: 6px; background: rgba(59,130,246,0.15); color: var(--accent); padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 16px; border: 1px solid rgba(59,130,246,0.3); }
        .dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; display: inline-block; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.85); } }
        h1 { font-size: 20px; font-weight: 700; margin-bottom: 8px; }
        p.subtitle { color: var(--text-dim); font-size: 13px; margin-bottom: 24px; line-height: 1.4; }
        .form-group { margin-bottom: 16px; text-align: left; }
        label { display: block; font-size: 12px; font-weight: 600; color: var(--text-dim); margin-bottom: 6px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px 14px; background: #0a0e17; border: 1px solid var(--border); border-radius: 6px; color: #fff; font-size: 14px; outline: none; transition: border-color 0.2s; }
        input:focus { border-color: var(--accent); }
        button { width: 100%; padding: 11px; background: var(--accent); color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.2s; margin-top: 8px; }
        button:hover { background: var(--accent-hover); }
        .alert { padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 16px; }
        .alert-error { background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; }
        .alert-success { background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); color: #6ee7b7; }
        .stats-box { margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--border); font-size: 12px; color: var(--text-dim); }
        .stat-row { display: flex; justify-content: space-between; margin-bottom: 6px; }
        .stat-val { font-family: monospace; color: #cbd5e1; font-weight: 600; }
    </style>
</head>
<body>
    <div class="card">
        <div class="badge"><span class="dot"></span> NetWatch Attack Lab Target</div>
        <h1>Enterprise Portal</h1>
        <p class="subtitle">Mock authentication service for live intrusion detection and telemetry simulation.</p>

        __MESSAGE_BLOCK__

        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" placeholder="e.g. admin" required autocomplete="off">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="••••••••" required>
            </div>
            <button type="submit">Sign In</button>
        </form>

        <div class="stats-box">
            <div class="stat-row"><span>Requests Received:</span><span class="stat-val">__REQ_COUNT__</span></div>
            <div class="stat-row"><span>Auth Attempts:</span><span class="stat-val">__AUTH_COUNT__</span></div>
            <div class="stat-row"><span>Failed Logins:</span><span class="stat-val" style="color: #ef4444;">__FAIL_COUNT__</span></div>
            <div class="stat-row"><span>Uptime:</span><span class="stat-val">__UPTIME__s</span></div>
            <div class="stat-row"><span>Client IP:</span><span class="stat-val">__CLIENT_IP__</span></div>
        </div>
    </div>
</body>
</html>"""


def render_html(message_html: str = "") -> str:
    uptime = int(time.time() - START_TIME)
    html = HTML_TEMPLATE
    html = html.replace("__MESSAGE_BLOCK__", message_html)
    html = html.replace("__REQ_COUNT__", str(STATS["total_requests"]))
    html = html.replace("__AUTH_COUNT__", str(STATS["login_attempts"]))
    html = html.replace("__FAIL_COUNT__", str(STATS["login_failures"]))
    html = html.replace("__UPTIME__", str(uptime))
    html = html.replace("__CLIENT_IP__", str(STATS["last_client_ip"] or "None"))
    return html


# ── Zero-dependency Standard Library HTTP Server ─────────────────────────────
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


class TargetAppHandler(BaseHTTPRequestHandler):
    timeout = 2.0

    def log_message(self, format, *args):
        # Concise logging
        logger.info(f"{self.client_address[0]} - {args[0]} {args[1]}")

    def _record_traffic(self):
        STATS["total_requests"] += 1
        if self.command == "GET":
            STATS["get_requests"] += 1
        elif self.command == "POST":
            STATS["post_requests"] += 1

        client_ip = self.client_address[0]
        STATS["unique_ips"].add(client_ip)
        STATS["last_client_ip"] = client_ip
        STATS["last_request_time"] = datetime.now().isoformat()

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        STATS["requests_by_path"][path] = STATS["requests_by_path"].get(path, 0) + 1
        return path

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self._record_traffic()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

    def do_GET(self):
        path = self._record_traffic()

        if path == "/" or path == "/login":
            self._send_html(render_html())
        elif path == "/api/health":
            self._send_json({
                "status": "online",
                "service": "netwatch_attack_target",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": int(time.time() - START_TIME),
            })
        elif path == "/api/status":
            self._send_json({
                "service": "netwatch_attack_target",
                "uptime_seconds": int(time.time() - START_TIME),
                "total_requests": STATS["total_requests"],
                "get_requests": STATS["get_requests"],
                "post_requests": STATS["post_requests"],
                "login_attempts": STATS["login_attempts"],
                "login_failures": STATS["login_failures"],
                "login_successes": STATS["login_successes"],
                "unique_ips_count": len(STATS["unique_ips"]),
                "last_client_ip": STATS["last_client_ip"],
                "last_request_time": STATS["last_request_time"],
                "requests_by_path": STATS["requests_by_path"],
            })
        elif path == "/api/users":
            self._send_json({
                "total": 5,
                "users": [
                    {"id": 1, "username": "admin", "role": "Domain Admin", "department": "IT Operations"},
                    {"id": 2, "username": "jsmith", "role": "Network Engineer", "department": "Infrastructure"},
                    {"id": 3, "username": "agarcia", "role": "Security Analyst", "department": "SOC"},
                    {"id": 4, "username": "rithik", "role": "Developer", "department": "Engineering"},
                    {"id": 5, "username": "finance_svc", "role": "Service Account", "department": "Finance"},
                ]
            })
        elif path == "/api/documents":
            self._send_json({
                "total_files": 4,
                "classification": "CONFIDENTIAL",
                "files": [
                    {"id": "doc_01", "name": "Q3_Network_Architecture.pdf", "size_kb": 1240},
                    {"id": "doc_02", "name": "Firewall_Rule_Backup_2026.json", "size_kb": 350},
                    {"id": "doc_03", "name": "Customer_PII_Export.csv", "size_kb": 8900},
                    {"id": "doc_04", "name": "API_Credentials_Master.env", "size_kb": 12},
                ]
            })
        else:
            self._send_json({"error": "Not Found", "path": path}, status=404)

    def do_POST(self):
        path = self._record_traffic()
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        # Parse form data or json
        username = ""
        password = ""
        is_json = "application/json" in self.headers.get("Content-Type", "")

        if is_json:
            try:
                parsed_json = json.loads(post_data)
                username = parsed_json.get("username", "")
                password = parsed_json.get("password", "")
            except Exception:
                pass
        else:
            try:
                parsed_form = urllib.parse.parse_qs(post_data)
                username = parsed_form.get("username", [""])[0]
                password = parsed_form.get("password", [""])[0]
            except Exception:
                pass

        if path == "/login":
            STATS["login_attempts"] += 1
            if username == "admin" and password == "SecretCorp2026!":
                STATS["login_successes"] += 1
                if is_json or "application/json" in self.headers.get("Accept", ""):
                    self._send_json({"status": "success", "token": "token_admin_authorized_99812", "user": "admin"})
                else:
                    msg = f'<div class="alert alert-success">Authenticated successfully as {username}!</div>'
                    self._send_html(render_html(msg))
            else:
                STATS["login_failures"] += 1
                if is_json or "application/json" in self.headers.get("Accept", ""):
                    self._send_json({"error": "Invalid username or password", "status": "failed"}, status=401)
                else:
                    msg = '<div class="alert alert-error">Invalid username or password</div>'
                    self._send_html(render_html(msg), status=401)
        elif path == "/api/reset":
            global START_TIME
            START_TIME = time.time()
            STATS["total_requests"] = 0
            STATS["get_requests"] = 0
            STATS["post_requests"] = 0
            STATS["login_attempts"] = 0
            STATS["login_failures"] = 0
            STATS["login_successes"] = 0
            STATS["unique_ips"].clear()
            STATS["last_client_ip"] = None
            STATS["last_request_time"] = None
            STATS["requests_by_path"].clear()
            self._send_json({"status": "reset", "message": "Statistics reset successfully"})
        else:
            self._send_json({"error": "Not Found", "path": path}, status=404)


def main():
    parser = argparse.ArgumentParser(description="NetWatch Attack Lab Target Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()

    print("========================================")
    print("  NETWATCH ATTACK LAB — TARGET APP")
    print(f"  Listening on: http://{args.host}:{args.port}")
    print("  Endpoints:    / (login form), /api/status, /api/health, /api/users, /api/documents")
    print("========================================")
    sys.stdout.flush()

    server = ThreadedHTTPServer((args.host, args.port), TargetAppHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTarget server shutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
