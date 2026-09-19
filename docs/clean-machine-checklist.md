# Clean-Machine Verification Checklist

Use this to verify the project works on a fresh machine (Windows/Linux/macOS).

---

## Prerequisites (Manual)
- [ ] Git installed
- [ ] Python 3.10+ installed (https://python.org)
- [ ] Node.js 20+ installed (for frontend dev, optional)

---

## Windows Verification

```powershell
# 1. Clone
git clone <REPO_URL>
cd <PROJECT>

# 2. Run setup
.\scripts\setup_windows.ps1

# Expected output:
# [1/7] Checking Python... PASS
# [2/7] Creating virtual environment... PASS
# [3/7] Installing Python dependencies... PASS
# [4/7] Checking TShark... NOT FOUND
# [5/7] Installing Wireshark/TShark... PASS  (winget UAC prompt appears)
# [6/7] Configuring TShark... PASS  (TSHARK_PATH in .env, added to USER PATH)
# [7/7] Verifying... PASS
# SETUP COMPLETE

# 3. Verify
python scripts/check_tshark.py
# Should show: TShark: AVAILABLE, Live Capture: READY

# 4. Run
.\venv\Scripts\Activate.ps1
python run.py

# 5. Open browser
# http://localhost:5000/live     → Live Monitor
# http://localhost:5000/url-monitor → URL Monitor
# http://localhost:5000/system   → System (TShark status visible)

# 6. Test Live Monitor
# - Select interface (e.g., "Ethernet" or "Wi-Fi")
# - Click "Start capture"
# - Should see: packets, flows, risk, stage updating
# - Click "Stop capture"
```

### Windows Success Criteria
- [ ] `winget` or `choco` installed Wireshark (UAC prompt appeared)
- [ ] `TSHARK_PATH` written to `.env`
- [ ] Wireshark directory added to USER PATH (persists across shells)
- [ ] `python scripts/check_tshark.py` → **SETUP COMPLETE**
- [ ] Dashboard starts without errors
- [ ] `/live` page: TShark status shows green dot + version
- [ ] `/live` page: "Start capture" button enabled
- [ ] Live capture produces packets on active interface

---

## Linux Verification (Debian/Ubuntu/Kali/Fedora/Arch)

```bash
# 1. Clone
git clone <REPO_URL>
cd <PROJECT>

# 2. Run setup
chmod +x scripts/setup_linux.sh
./scripts/setup_linux.sh

# Expected output:
# [1/7] Checking Python... PASS
# [2/7] Creating virtual environment... PASS
# [3/7] Installing Python dependencies... PASS
# [4/7] Checking TShark... NOT FOUND
# [5/7] Installing TShark... PASS  (sudo apt-get install tshark)
# [6/7] Configuring TShark... PASS  (TSHARK_PATH in .env)
# [7/7] Verifying... PASS
# SETUP COMPLETE

# 3. Grant capture permission (one-time)
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap

# 4. Verify
python scripts/check_tshark.py
# Should show: TShark: AVAILABLE, Live Capture: READY

# 5. Run
source venv/bin/activate
python run.py

# 6. Open browser
# http://localhost:5000/live
# http://localhost:5000/url-monitor
# http://localhost:5000/system
```

### Linux Success Criteria
- [ ] `apt`/`dnf`/`pacman` installed `tshark`/`wireshark-cli`
- [ ] `TSHARK_PATH` written to `.env`
- [ ] `setcap` granted to `dumpcap` (or running with sudo)
- [ ] `python scripts/check_tshark.py` → **SETUP COMPLETE**
- [ ] Dashboard starts without errors
- [ ] `/live` page: TShark status shows green dot + version
- [ ] `/live` page: "Start capture" button enabled
- [ ] Live capture produces packets on active interface (eth0, wlan0, etc.)

---

## macOS Verification

```bash
# 1. Clone
git clone <REPO_URL>
cd <PROJECT>

# 2. Run setup (requires Homebrew)
chmod +x scripts/setup_linux.sh  # works on macOS too
./scripts/setup_linux.sh
# Or manually: brew install wireshark

# 3. Verify
python scripts/check_tshark.py

# 4. Run
source venv/bin/activate
python run.py

# 5. Open browser to http://localhost:5000/live
```

### macOS Notes
- Homebrew installs TShark to `/opt/homebrew/bin/tshark` (Apple Silicon) or `/usr/local/bin/tshark` (Intel)
- Live capture may require additional permissions (see [troubleshooting](troubleshooting.md))

---

## Docker Verification (Linux Host Only)

```bash
# 1. Build & run development
docker compose up dev
# http://localhost:5000

# 2. Live capture profile (requires host network + capabilities)
docker compose --profile live up live
# http://localhost:5000/api/live/health should show available: true
```

---

## Cross-Platform Verification (Python Setup)

```bash
# Works on any platform with Python 3.10+
python scripts/setup.py

# Verification
python scripts/check_tshark.py

# Run
python run.py
```

---

## Functional Tests (All Platforms)

### Offline Modes (No TShark Required)
- [ ] `python run.py --pipeline-only` → prints forecast report, exits
- [ ] `python forecast.py --input data.csv --horizon 5` → works with CSV
- [ ] `python forecast_pcap.py --input capture.pcap --horizon 5` → works with PCAP
- [ ] Dashboard `/demo` page → synthetic scenarios load
- [ ] Dashboard `/upload` page → PCAP/CSV upload + analysis

### Live Modes (TShark Required)
- [ ] `/live` → interface dropdown populated
- [ ] `/live` → "Start capture" works, shows real-time packets
- [ ] `/live` → SSE stream updates (`/api/live/events`)
- [ ] `/url-monitor` → enter `https://example.com` → "START URL MONITOR" works
- [ ] `/url-monitor` → DNS resolution logged, traffic metrics appear
- [ ] `/system` → TShark section shows green dot, version, path, interfaces

### API Health
- [ ] `GET /api/live/health` → `{ "available": true, "path": "...", "version": "..." }`
- [ ] `GET /api/system/dependencies` → python + tshark + live_capture all available

---

## Expected File Structure After Setup

```
project/
├── .env                    # Created by setup (TSHARK_PATH=...)
├── venv/                   # Python virtual environment
├── data/
│   ├── generated/          # Pipeline outputs (gitignored)
│   └── models/             # Trained model artifacts (gitignored)
├── frontend/dist/          # Built SPA (after npm run build)
└── netwatch_server.log     # Runtime logs (gitignored)
```

---

## CI Verification (GitHub Actions)

```yaml
# .github/workflows/ci.yml
# On push/PR:
# - Unit tests (3 Python versions) ✓
# - Lint (ruff + mypy) ✓
# - Frontend build ✓
# - Docker build (dev + live-capture) ✓

# Manual / with secret:
# - TShark integration tests (installs tshark, runs live tests)
```

---

## Sign-Off

| Platform | Verified By | Date | Notes |
|----------|-------------|------|-------|
| Windows 11 |  |  |  |
| Ubuntu 22.04 |  |  |  |
| Fedora 39 |  |  |  |
| macOS 14 |  |  |  |
| Docker (Linux) |  |  |  |

---

## Known Limitations

1. **Docker Desktop (Mac/Windows)**: `network_mode: host` doesn't work — live capture not possible. Use native or Linux VM.
2. **Windows Npcap**: Must be installed via Wireshark installer (winget/choco do this). Standalone Npcap installer also works.
3. **Non-root Linux**: Requires `setcap` on `dumpcap` or running with `sudo` (not recommended for the full app).
4. **First run**: World Model trains lazily (~30–120s on first dashboard request). Use `python run.py --pipeline-only` to pre-train.