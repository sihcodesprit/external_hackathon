"""
NetWatch Attack Lab Manager — Backend Controller.

Coordinates the Attack Lab environment:
  - Target application lifecycle (start, stop, health, metrics)
  - Attack execution (recon, brute force, DoS flood, data exfiltration)
  - Topology inspection (veth pair, network namespace, interfaces)
  - Real-time event and output streaming to the dashboard
"""

import json
import logging
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts" / "attack_lab"
TARGET_APP_SCRIPT = SCRIPTS_DIR / "target_app.py"
ATTACK_RUNNER_SCRIPT = SCRIPTS_DIR / "attack_runner.py"
SETUP_LAB_SCRIPT = SCRIPTS_DIR / "setup_lab.sh"


def _get_python_bin() -> str:
    venv_py = ROOT_DIR / "venv" / "bin" / "python"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


class LabManager:
    """Singleton manager for Attack Lab operations."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._target_process: Optional[subprocess.Popen] = None
        self._target_started_at: Optional[str] = None
        self._target_port = 8080
        self._target_host = "0.0.0.0"

        self._attack_thread: Optional[threading.Thread] = None
        self._attack_process: Optional[subprocess.Popen] = None
        self._attack_session_obj = None
        self._attack_running = False
        self._attack_started_at: Optional[str] = None
        self._current_attack_type: Optional[str] = None
        self._current_target_ip = "10.0.0.2"

        self._log_buffer = deque(maxlen=300)
        self._events_history = []
        self._state_lock = threading.RLock()

        # Add initial greeting log
        self._append_log("Attack Lab Controller initialized.")

    def _append_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        with self._state_lock:
            self._log_buffer.append(entry)
        logger.info(f"[LabManager] {message}")

    # ── Topology & Environment Inspection ─────────────────────────────────────
    def get_topology_status(self) -> Dict:
        """Inspects network namespaces, veth interfaces, and tools."""
        has_netns = False
        has_veth = False
        active_iface = "lo"

        # Check for netns 'attacker'
        if sys.platform.startswith("linux"):
            try:
                res = subprocess.run(
                    ["ip", "netns", "list"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if "attacker" in res.stdout:
                    has_netns = True
            except Exception:
                pass

            try:
                res = subprocess.run(
                    ["ip", "link", "show", "lab-veth0"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0:
                    has_veth = True
                    active_iface = "lab-veth0"
            except Exception:
                pass

        # Target connectivity check
        target_running, target_stats = self.check_target_health()

        return {
            "netns_available": has_netns,
            "netns_name": "attacker" if has_netns else None,
            "veth_interface": "lab-veth0" if has_veth else None,
            "has_veth": has_veth,
            "suggested_interface": active_iface,
            "attacker_ip": "10.0.0.1" if has_veth else "127.0.0.1",
            "target_ip": "10.0.0.2" if has_veth else "127.0.0.1",
            "target_port": self._target_port,
            "target_running": target_running,
            "target_stats": target_stats,
            "has_nmap": shutil.which("nmap") is not None,
            "has_hping3": shutil.which("hping3") is not None,
            "has_hydra": shutil.which("hydra") is not None,
        }

    # ── Target Web Server Control ─────────────────────────────────────────────
    def check_target_health(self) -> (bool, Optional[Dict]):
        """Queries the target app /api/status endpoint using fast non-blocking probes."""
        if self._target_process and self._target_process.poll() is not None:
            self._target_process = None

        # Fast probe on 127.0.0.1 (always reachable when target is bound to 0.0.0.0 or 127.0.0.1)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.08)
            res = s.connect_ex(("127.0.0.1", self._target_port))
            s.close()
            if res == 0:
                url = f"http://127.0.0.1:{self._target_port}/api/status"
                req = urllib.request.Request(url, headers={"User-Agent": "NetWatch-HealthCheck", "Connection": "close"})
                with urllib.request.urlopen(req, timeout=0.3) as resp:
                    if resp.getcode() == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        return True, data
        except Exception:
            pass

        if self._target_process and self._target_process.poll() is None:
            return True, {"service": "target_app", "status": "running", "pid": self._target_process.pid}

        return False, None

    def start_target_server(self, port: int = 8080, host: str = "0.0.0.0") -> Dict:
        """Launches the target Flask web server."""
        with self._state_lock:
            if self._target_process and self._target_process.poll() is None:
                return {
                    "status": "already_running",
                    "pid": self._target_process.pid,
                    "port": self._target_port,
                    "host": self._target_host,
                }

            self._target_port = port
            self._target_host = host
            self._append_log(f"Starting target web application on {host}:{port}...")

            cmd = [_get_python_bin(), str(TARGET_APP_SCRIPT), "--host", host, "--port", str(port)]
            try:
                self._target_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
                self._target_started_at = datetime.now().isoformat()
            except Exception as e:
                self._append_log(f"Failed to start target app: {e}")
                return {"status": "error", "error": str(e)}

        # Wait briefly for startup
        time.sleep(0.8)
        is_up, stats = self.check_target_health()
        if is_up:
            self._append_log(f"Target web application successfully RUNNING (PID: {self._target_process.pid})")
            return {
                "status": "running",
                "pid": self._target_process.pid,
                "port": self._target_port,
                "stats": stats,
            }
        else:
            self._append_log(f"Target process started (PID: {self._target_process.pid}), awaiting first request.")
            return {
                "status": "starting",
                "pid": self._target_process.pid,
                "port": self._target_port,
            }

    def stop_target_server(self) -> Dict:
        """Stops the target Flask web server."""
        with self._state_lock:
            if not self._target_process or self._target_process.poll() is not None:
                self._target_process = None
                return {"status": "stopped", "message": "Target server is not running"}

            self._append_log(f"Stopping target web application (PID: {self._target_process.pid})...")
            try:
                self._target_process.terminate()
                self._target_process.wait(timeout=3)
            except Exception:
                try:
                    self._target_process.kill()
                except Exception:
                    pass

            pid = self._target_process.pid
            self._target_process = None
            self._append_log("Target web application stopped.")
            return {"status": "stopped", "pid": pid}

    # ── Attack Simulation Execution ───────────────────────────────────────────
    def start_attack(self, attack_type: str, target_ip: Optional[str] = None,
                     duration: int = 15, intensity: str = "medium") -> Dict:
        """Starts a simulated attack session in the background."""
        valid_attacks = {"recon", "bruteforce", "dos", "exfiltration"}
        if attack_type not in valid_attacks:
            return {"status": "error", "error": f"Invalid attack type '{attack_type}'. Must be one of {valid_attacks}"}

        with self._state_lock:
            if self._attack_running:
                return {
                    "status": "busy",
                    "error": f"An attack ({self._current_attack_type}) is already currently running. Stop it first.",
                    "active_attack": self._current_attack_type,
                }

            # Determine best target IP
            topo = self.get_topology_status()
            if not target_ip:
                target_ip = topo["target_ip"]
            self._current_target_ip = target_ip
            self._current_attack_type = attack_type
            self._attack_running = True
            self._attack_started_at = datetime.now().isoformat()

        self._append_log(f">>> LAUNCHING {attack_type.upper()} ATTACK against {target_ip}:{self._target_port} (Duration: {duration}s, Intensity: {intensity})")

        # Import attack session runner
        try:
            from scripts.attack_lab.attack_runner import AttackSession
        except ImportError:
            # Fallback path import
            sys.path.insert(0, str(ROOT_DIR))
            from scripts.attack_lab.attack_runner import AttackSession

        session = AttackSession(
            attack_type=attack_type,
            target_ip=target_ip,
            target_port=self._target_port,
            duration=duration,
            intensity=intensity,
            log_callback=self._append_log,
        )
        self._attack_session_obj = session

        def worker():
            try:
                res = session.run()
                with self._state_lock:
                    self._events_history.append({
                        "id": len(self._events_history) + 1,
                        "timestamp": datetime.now().isoformat(),
                        "attack_type": attack_type,
                        "target": f"{target_ip}:{self._target_port}",
                        "duration": res.get("elapsed_seconds", duration),
                        "packets_sent": res.get("packets_sent", 0),
                        "status": "completed",
                    })
            except Exception as e:
                self._append_log(f"Attack worker execution error: {e}")
            finally:
                with self._state_lock:
                    self._attack_running = False
                    self._attack_session_obj = None

        self._attack_thread = threading.Thread(target=worker, daemon=True, name=f"attack-{attack_type}")
        self._attack_thread.start()

        return {
            "status": "started",
            "attack_type": attack_type,
            "target_ip": target_ip,
            "target_port": self._target_port,
            "duration": duration,
            "intensity": intensity,
            "started_at": self._attack_started_at,
        }

    def stop_attack(self) -> Dict:
        """Terminates any active attack simulation."""
        with self._state_lock:
            if not self._attack_running and not self._attack_session_obj:
                return {"status": "idle", "message": "No attack is currently running"}

            self._append_log("Stop requested for active attack session.")
            if self._attack_session_obj:
                try:
                    self._attack_session_obj.stop()
                except Exception as e:
                    logger.warning(f"Error stopping session obj: {e}")

            self._attack_running = False
            attack_type = self._current_attack_type
            self._current_attack_type = None

        return {"status": "stopped", "attack_type": attack_type}

    def clear_logs_and_stats(self) -> Dict:
        """Clears the console log buffer, event history, and resets target stats."""
        with self._state_lock:
            self._log_buffer.clear()
            self._events_history.clear()
            self._append_log("Console logs and telemetry reset.")

        # Reset target web server stats
        try:
            url = f"http://127.0.0.1:{self._target_port}/api/reset"
            req = urllib.request.Request(url, data=b"{}", headers={"User-Agent": "NetWatch-Reset", "Connection": "close", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=0.5) as _:
                pass
        except Exception:
            pass

        return {"status": "cleared", "message": "Logs and target statistics reset."}

    # ── Overall Status ────────────────────────────────────────────────────────
    def get_full_status(self) -> Dict:
        """Returns consolidated lab status for the frontend."""
        topo = self.get_topology_status()
        with self._state_lock:
            logs = list(self._log_buffer)
            events = list(reversed(self._events_history[-20:]))
            is_running = self._attack_running
            attack_type = self._current_attack_type
            started_at = self._attack_started_at
            packets_sent = self._attack_session_obj.packets_sent if self._attack_session_obj else 0

        return {
            "topology": topo,
            "active_attack": {
                "running": is_running,
                "type": attack_type,
                "started_at": started_at,
                "packets_sent": packets_sent,
            } if is_running else None,
            "recent_events": events,
            "logs": logs[-60:],
        }
