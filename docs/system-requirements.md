# System Requirements

This document lists all system-level (non-Python) requirements for running the
Counterfactual Cyber World Model with live network monitoring.

---

## Core Requirements

### Python
- **Python ≥ 3.10** (3.10, 3.11, 3.12 tested)
- `venv` module (standard library)

### Network Capture (Live Monitoring)

The live monitoring pipeline requires **TShark** (the CLI component of Wireshark).
It is **not** required for offline analysis (PCAP, CSV, JSONL, synthetic modes).

| Platform | Package | Install Command |
|----------|---------|-----------------|
| Debian / Ubuntu / Kali | `tshark` | `sudo apt-get install -y tshark` |
| Fedora / RHEL / CentOS Stream | `wireshark-cli` | `sudo dnf install -y wireshark-cli` |
| Arch Linux | `wireshark-cli` | `sudo pacman -Sy wireshark-cli` |
| openSUSE | `wireshark` | `sudo zypper install -y wireshark` |
| macOS (Homebrew) | `wireshark` | `brew install wireshark` |
| Windows (winget) | `WiresharkFoundation.Wireshark` | `winget install --id WiresharkFoundation.Wireshark` |
| Windows (Chocolatey) | `wireshark` | `choco install wireshark -y` |

#### Windows: Npcap / WinPcap
TShark on Windows requires a packet capture driver. The Wireshark installer includes
**Npcap** (recommended) or legacy **WinPcap**. The setup script detects Npcap DLLs
automatically.

#### Linux: Capture Permissions
By default, capturing packets requires root (`sudo`) or the `CAP_NET_RAW` +
`CAP_NET_ADMIN` capabilities on the `dumpcap` binary (installed with TShark).

```bash
# Option 1: Run as root (not recommended for the app itself)
sudo python run.py

# Option 2: Grant capabilities to dumpcap (recommended)
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap
```

The Docker `live` service uses `cap_add: [NET_RAW, NET_ADMIN]` and
`network_mode: host` for this reason.

---

## Python Dependencies

All Python dependencies are listed in `requirements.txt` and installed
automatically by the setup scripts:

```
flask>=3.0,<4
gunicorn>=21.0
werkzeug>=3.0
numpy>=1.26
scikit-learn>=1.4
torch>=2.1
pyyaml>=6.0
shap>=0.46
scapy>=2.5       # PCAP ingestion
psutil>=5.9      # interface discovery (optional; fallbacks exist)
pytest>=7.4      # testing
```

---

## Optional / Development

| Tool | Purpose |
|------|---------|
| `ruff` | Fast Python linting |
| `mypy` | Static type checking |
| `waitress` | Production WSGI server (used by `run.py` if available) |
| Docker / Docker Compose | Containerised deployment |
| Node.js 20 + npm | Frontend development (React + Vite) |

---

## Frontend (Development Only)

- **Node.js ≥ 20**
- **npm** (bundled with Node.js)

```bash
cd frontend
npm install
npm run dev      # Dev server with HMR
npm run build    # Production build to frontend/dist/
```

The Flask app serves the built SPA from `frontend/dist/` in production.

---

## Disk Space

| Component | Approx. Size |
|-----------|--------------|
| Python venv + deps | ~500 MB |
| Wireshark / TShark | ~200–400 MB |
| Model artifacts (generated) | ~50–200 MB |
| PCAP / CSV uploads | User-dependent |

---

## Network

- **Dashboard**: Port 5000 (configurable via `PORT` env var)
- **Live capture**: Requires access to a local network interface
- **URL Monitor**: Requires DNS resolution (outbound UDP/53) for the target hostname

---

## Verification

After installation, run the built-in verification:

```bash
python scripts/check_tshark.py
```

Expected output when TShark is ready:

```
========================================
CYBER WORLD MODEL ENVIRONMENT CHECK
========================================

Operating System:
  Linux 6.8.0 (x86_64)

Python:
  3.11.9 (CPython)

TShark:
  AVAILABLE

TShark Path:
  /usr/bin/tshark

TShark Version:
  4.2.3

Platform:
  linux

Live Capture:
  READY

Available Interfaces:
  ● eth0 (192.168.1.42)
  ● wlan0 (10.0.0.5)

========================================
SETUP COMPLETE
========================================
```