# Live TShark Monitoring

Real-time network attack forecasting with **TShark as the ONLY live packet
capture source**. No Zeek, no Suricata, no raw-socket capture — the live
pipeline reads TShark's streaming JSON line output and pushes every parsed
packet through the existing Cyber World Model feature/build/forecast chain.

---

## Quick Start (One-Command Setup)

The project now includes a **cross-platform bootstrap system** that automatically
installs Python dependencies, discovers/installs TShark, and configures everything.

```bash
# Linux / macOS
git clone <repo>
cd <project>
chmod +x scripts/setup_linux.sh
./scripts/setup_linux.sh

# Windows PowerShell
git clone <repo>
cd <project>
.\scripts\setup_windows.ps1

# Cross-platform (Python)
python scripts/setup.py
```

After setup, verify:
```bash
python scripts/check_tshark.py
```

Then start the dashboard:
```bash
python run.py
# Open http://localhost:5000
# Live Monitor:  http://localhost:5000/live
# URL Monitor:   http://localhost:5000/url-monitor
# System:        http://localhost:5000/system
```

---

## Requirements

### Python
- **Python ≥ 3.10** (3.10, 3.11, 3.12 tested)

### TShark (Live Capture Only)
| Platform | Package | Install |
|----------|---------|---------|
| Debian/Ubuntu/Kali | `tshark` | `apt-get install -y tshark` |
| Fedora/RHEL | `wireshark-cli` | `dnf install -y wireshark-cli` |
| Arch | `wireshark-cli` | `pacman -Sy wireshark-cli` |
| openSUSE | `wireshark` | `zypper install -y wireshark` |
| macOS (Homebrew) | `wireshark` | `brew install wireshark` |
| Windows (winget) | `WiresharkFoundation.Wireshark` | `winget install --id WiresharkFoundation.Wireshark` |
| Windows (Chocolatey) | `wireshark` | `choco install wireshark -y` |

**The setup scripts handle this automatically.**

### Capture Permissions
| Platform | Requirement |
|----------|-------------|
| Linux | `sudo` or `setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap` |
| Windows | Run as Administrator, or grant "Capture" privilege |
| Docker | `cap_add: [NET_RAW, NET_ADMIN]` + `network_mode: host` (Linux only) |

---

## Architecture

```
TShark (-i <iface> -T ek -l)
   │  one JSON object per line (EK control frames + data frames)
   ▼
TSharkSensor ── parses JSON lines, dispatches callbacks
   ▼
LivePipeline.process_event()
   ├─ parse_ek_line()        → flat packet dict (skips EK index lines)
   ├─ event_to_packet_record() → PacketRecord
   ├─ WindowManager          → sliding 30s window / 5s step
   ├─ FlowTracker            → bounded flow/host accounting
   ▼
check_window() every step
   ├─ StateBuilder           → NetworkState per window
   ├─ fit linear world model (per LIVE_MODEL_REFIT_INTERVAL windows)
   ├─ AttackForecaster       → K-step risk forecast
   └─ MITRE / graph / explainability / counterfactual / ensemble
```

The `LiveManager` singleton owns one session: a background worker processes
window steps, a dashboard loop pushes SSE updates to subscribed browsers.

---

## Configuration

All options live in `configs/config.yaml` under `live:` and can be
overridden by environment variables (`.env` file at repo root):

| Env var | Default | Purpose |
| --- | --- | --- |
| `TSHARK_PATH` | *(empty, auto-discover)* | **Preferred:** explicit TShark executable path |
| `NETWATCH_TSHARK_PATH` | *(empty)* | Legacy alias (still supported) |
| `NETWATCH_LIVE_ENABLED` | `true` | Master kill-switch |
| `NETWATCH_LIVE_TSHARK_FORMAT` | `ek` | Output format (ek only supported) |
| `NETWATCH_LIVE_BPF_FILTER` | *(empty)* | Optional BPF filter, e.g. `"not port 22"` |
| `NETWATCH_LIVE_SNAPLEN` | `65535` | Snapshot length |
| `NETWATCH_LIVE_PROMISCUOUS` | `true` | Promiscuous mode |
| `NETWATCH_LIVE_DEFAULT_INTERFACE` | *(empty)* | Auto-select first usable iface |
| `NETWATCH_LIVE_WINDOW_SIZE` | `30` | Seconds per aggregation window |
| `NETWATCH_LIVE_STEP_SIZE` | `5` | Seconds between window starts |
| `NETWATCH_LIVE_FORECAST_HORIZON` | `5` | K-step rollout |
| `NETWATCH_LIVE_MIN_STATES_FOR_MODEL` | `8` | States before first model fit |
| `NETWATCH_LIVE_MODEL_REFIT_INTERVAL` | `3` | Re-fit the linear model every N windows |

**Priority for TShark executable:**
1. `TSHARK_PATH` environment variable (explicit)
2. `NETWATCH_TSHARK_PATH` environment variable (legacy)
3. `tshark` on `PATH`
4. Platform candidate paths (Program Files on Windows, `/usr/bin` etc. on Linux)
5. Setup script installation hint

---

## API Endpoints

All behind `/api/live/*`:

- `GET /api/live/health` — TShark availability + version probe
- `GET /api/live/interfaces` — discoverable interfaces
- `POST /api/live/start` — `{ "interface", "window_size", "step_size", "forecast_horizon" }`
- `POST /api/live/stop` — stop the current session
- `GET /api/live/status` — lightweight session status (frontend polls when idle)
- `GET /api/live/events` — **SSE stream** (`text/event-stream`) of live updates
- `GET /api/live/analysis/<id>` — full canonical analysis document
- `GET /api/live/history` — previous session summaries

### URL Monitor (Destination-Observed Capture)

- `POST /api/live/url/start` — `{ "url", "interface", "window_size", "step_size", "forecast_horizon" }`
- `GET /api/live/url/status/<analysis_id>` — full URL monitoring status
- `POST /api/live/url/stop` — stop URL monitoring session

### System Dependencies

- `GET /api/system/dependencies` — Python, TShark, live capture readiness

---

## Frontend

| Route | Page | Purpose |
|-------|------|---------|
| `/live` | `LiveMonitor` | Interface selection, start/stop, live metrics, risk, event log |
| `/url-monitor` | `UrlMonitor` | URL input → DNS resolve → TShark capture → live traffic metrics |
| `/system` | `System` | **New:** Runtime, model registry, artifacts, **TShark dependencies** |

### LiveMonitor
1. Verify TShark health + pick an interface (disabled if TShark unavailable)
2. Start/stop capture (button shows "Install TShark to enable" when missing)
3. Live metrics: packets, flows, hosts, network states, packets/sec
4. Current risk, current stage and window configuration
5. Live event log via SSE (`/api/live/events`)
6. Previous-session history

### UrlMonitor
1. Enter URL → validates scheme (http/https), rejects private/loopback
2. DNS resolution → builds BPF filter for resolved IPs + port
3. TShark capture with that filter
4. Real-time URL traffic metrics, risk, forecast

---

## Security Notes

- **No `shell=True`** — all subprocess calls use list arguments
- **Interface validation** — restricted to `[A-Za-z0-9_.-]`
- **BPF filter validation** — internally generated from resolved IPs, length-capped
- **URL validation** — only `http`/`https`; hostname regex; SSRF protection
- **Capture privileges** — documented separately; app runs as normal user

---

## Testing

```bash
# Unit tests (no TShark required — uses MockTsharkRunner)
python -m pytest tests/test_live.py -q

# TShark integration tests (requires TShark + capture permission)
TSHARK_INTEGRATION_TESTS=1 python -m pytest tests/ -m tshark_integration -v
```

### CI/CD
- **Unit tests** run on every push/PR (GitHub Actions, `ubuntu-latest`, Python 3.10–3.12)
- **TShark integration tests** run only when `TSHARK_INTEGRATION_TESTS=true` secret is set
- **Lint**: `ruff` + `mypy` (basic)
- **Frontend build**: `npm run build` verification
- **Docker**: builds `development`, `live-capture`, `production` targets

---

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues:

- `TShark: NOT AVAILABLE` → run setup script or install manually
- `Permission denied` → grant capabilities to `dumpcap` or run with sudo
- `No interfaces detected` → check `ip link` / `tshark -D`
- `Frontend build not found` → run `cd frontend && npm run build`

---

## Docker (Live Capture)

```bash
# Development (no live capture)
docker compose up dev

# Live capture (Linux host only — needs host network + capabilities)
docker compose --profile live up live
```

**Note:** On Docker Desktop (macOS/Windows), `network_mode: host` does not expose host interfaces. Run natively or in a Linux VM for live capture.