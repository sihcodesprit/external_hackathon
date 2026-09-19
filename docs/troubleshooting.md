# Troubleshooting

Common issues and solutions for the Cyber World Model project.

---

## TShark / Live Monitoring

### `TShark: NOT AVAILABLE` or `TShark not found`

**Cause:** TShark executable not on PATH and not found in standard install locations.

**Fix:**
1. Run the setup script:
   ```bash
   # Linux/macOS
   ./scripts/setup_linux.sh
   
   # Windows PowerShell
   .\scripts\setup_windows.ps1
   
   # Cross-platform Python
   python scripts/setup.py
   ```
2. Or install manually (see [System Requirements](system-requirements.md))
3. Re-run verification: `python scripts/check_tshark.py`

---

### `TShark found but capture unavailable` (Windows)

**Cause:** Npcap/WinPcap driver not installed or not detected.

**Fix:**
1. Re-run Wireshark installer and ensure **Npcap** is selected (default).
2. Verify DLL exists:
   ```powershell
   Test-Path "C:\Windows\System32\Npcap\wpcap.dll"
   Test-Path "C:\Program Files\Npcap\wpcap.dll"
   ```
3. If using WinPcap (legacy), upgrade to Npcap.

---

### `Permission denied — need root or CAP_NET_RAW` (Linux)

**Cause:** Non-root user cannot open raw sockets for packet capture.

**Fix:**
```bash
# Option 1: Grant capabilities to dumpcap (persistent, no root needed)
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap

# Option 2: Run with sudo (not recommended for the full app)
sudo python run.py
```

**Docker:** The `live` service in `docker-compose.yml` uses `cap_add: [NET_RAW, NET_ADMIN]` and `network_mode: host`.

---

### `No interfaces detected` / `Interface not found`

**Cause:** No suitable network interfaces found, or interface name invalid.

**Fix:**
1. List interfaces: `python -c "from netwatch.live.interface import discover_interfaces; print(discover_interfaces())"`
2. Use an interface that is `UP` and not loopback (`lo`).
3. On Windows, interface names may look like `Ethernet`, `Wi-Fi`, `\Device\NPF_{GUID}`.
4. Set `NETWATCH_LIVE_DEFAULT_INTERFACE` in `.env` or select in the UI.

---

### `TShark exited with code 1: ...` / `TShark failed to start`

**Common causes:**
- Interface doesn't exist or is down
- BPF filter syntax error
- Another process holds the interface
- Insufficient permissions (see above)

**Debug:**
```bash
# Test TShark manually
tshark -i <interface> -D
tshark -i <interface> -T ek -c 5
```

---

### `Winget/Chocolatey install failed` (Windows)

**Cause:** Package manager not available, no admin rights, or network issue.

**Fix:**
1. Run PowerShell as Administrator.
2. Install manually from https://www.wireshark.org/download.html
3. After install, re-run `python scripts/check_tshark.py` to auto-detect.

---

## Python / Dependencies

### `ModuleNotFoundError: No module named 'torch'`

**Cause:** Requirements not installed or installed in wrong environment.

**Fix:**
```bash
# Ensure venv is active
# Linux/macOS
source venv/bin/activate
# Windows
.\venv\Scripts\Activate.ps1

# Re-install
pip install -r requirements.txt
```

---

### `ImportError: cannot import name '...' from 'netwatch.live'`

**Cause:** Stale `.pyc` files or partial install.

**Fix:**
```bash
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete
pip install -e .  # if using editable install
```

---

### `Python 3.10+ required`

**Cause:** System Python is older than 3.10.

**Fix:** Install Python 3.10+ from:
- Linux: `apt-get install python3.11` / `dnf install python3.11`
- macOS: `brew install python@3.11`
- Windows: https://python.org/downloads/

---

## Dashboard / Frontend

### `Frontend build not found. Run: npm run build`

**Cause:** React app not built; Flask tries to serve `frontend/dist/index.html`.

**Fix:**
```bash
cd frontend
npm install
npm run build
```
Then restart `python run.py`.

---

### `Port 5000 already in use`

**Cause:** Another process on port 5000.

**Fix:**
```bash
# Change port
PORT=8080 python run.py
# or
python run.py --port 8080
```

---

### Blank page / React errors in console

**Cause:** API calls failing (CORS, 404, 500).

**Debug:**
1. Open browser DevTools → Network tab
2. Check failed requests to `/api/*`
3. Check Flask console for tracebacks
4. Verify `FLASK_SECRET_KEY` is set in `.env`

---

## Docker

### `docker: Cannot connect to the Docker daemon`

**Cause:** Docker not running or user not in `docker` group.

**Fix:**
```bash
sudo systemctl start docker
# or on Windows/macOS: start Docker Desktop
```

---

### `Live capture in Docker: no interfaces / permission denied`

**Cause:** Container lacks host network access or capabilities.

**Fix:** Use the `live` profile which has `network_mode: host` and `cap_add`:
```bash
docker compose --profile live up live
```
**Note:** Host network mode only works on Linux Docker. On Docker Desktop (Mac/Windows),
live capture of the *host* interfaces is not directly supported — run natively or use a Linux VM.

---

### `Health check failed` in Docker

**Cause:** App not ready within `start_period`.

**Fix:** Increase `start_period` in `docker-compose.yml` or check logs:
```bash
docker compose logs dev
```

---

## Configuration

### `.env` not loading

**Cause:** `.env` in wrong location or not read.

**Fix:**
- Place `.env` at repository root (same level as `run.py`).
- The `run.py` entry point loads it automatically.
- Docker: use `environment:` in `docker-compose.yml` instead.

---

### `TSHARK_PATH` set but not used

**Cause:** Path contains spaces, quotes, or is invalid.

**Fix:**
```bash
# Check what the locator sees
python -c "from netwatch.live.tshark_locator import detect_tshark; import os; print(detect_tshark(os.getenv('TSHARK_PATH', '')))"
```
- Use forward slashes or raw strings on Windows: `C:/Program Files/Wireshark/tshark.exe`
- Don't wrap in quotes in `.env`: `TSHARK_PATH=C:\Program Files\Wireshark\tshark.exe`

---

## Data / Models

### `No valid packet or flow records found`

**Cause:** Uploaded PCAP/CSV is empty, malformed, or unsupported format.

**Fix:**
1. Verify file: `tshark -r file.pcap -c 5`
2. CSV must have expected columns (see `netwatch/ingestion/parser.py`)
3. Try synthetic data: visit `/demo` in the dashboard

---

### `Model artifacts not found` / `World model not trained`

**Cause:** First run hasn't completed training, or `data/models/` empty.

**Fix:**
- Dashboard trains lazily on first request (may take 30–120s).
- Or run explicitly: `python run.py --pipeline-only`
- Check `data/models/` for `.pt` and `.pkl` files.

---

## Still Stuck?

1. Run the verification script for a full diagnostic:
   ```bash
   python scripts/check_tshark.py
   ```

2. Check the dashboard **System** page (`/system`) for dependency status.

3. Search existing issues or open a new one with:
   - OS / Python version
   - Output of `python scripts/check_tshark.py`
   - Relevant log snippets (Flask console, browser DevTools)