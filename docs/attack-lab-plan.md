# Attack Lab — Real-Packet Network Simulator + In-UI Attack Console

Status: **PLANNED — implementation starts tomorrow**

Goal: run NetWatch against **real attack packets** (not just the built-in synthetic
scenarios) inside a self-contained virtual network segment on this machine, fire
attacks from a new in-UI "Attack Lab" tab, and watch live detection. Optionally
mirror the same setup on a free Oracle Cloud VM afterwards to play online.

Decisions already made:
- Run location: **local first, real target service** (a small web app we can attack).
- Attack triggering: **in-UI Attack Console** (browser buttons call the server).

---

## 1. Topology (local, real packets, distinct IPs)

```
attacker netns  10.0.0.1 ──veth──  lab-veth0  10.0.0.2   (host side)
                                        │
                                        ├─ netwatch server (root) — tshark live-captures lab-veth0
                                        └─ target web app — Flask login app on 10.0.0.2:8080
                                           (+ optional openssh-server on host for real SSH brute force)
```

- All attack traffic is confined to the veth pair — the real network is untouched.
- Attacker and target get distinct IPs, so host resolution / Traffic Summary read cleanly.

### Why root?
`tshark` live capture, raw-socket attack tools (`nmap -sS`, `hping3`, scapy), and
`ip netns exec` all need root. This machine has NO passwordless sudo
(`sudo` prompts for a password), and tshark is root-owned with no setcap/pcap-group.
Consequence: **the lab server itself runs as root** (start it with `sudo` once),
which sidesteps all of the above. The normal dev server stays unprivileged.

## 2. Environment facts (checked today)

- User: `rithik` (uid 1000), password-sudo only. Docker NOT installed / not in docker group.
- `nmap` installed at `/usr/bin/nmap`. `scapy 2.7.0` in `venv/.`
- `hping3` and `hydra` NOT installed → `sudo apt install hping3 hydra` in setup script.
- tshark 4.7.3 at `/usr/bin/tshark`, no pcap group, no setcap.
- `frontend/node_modules` is TRACKED in git (3402 files) even though `.gitignore`
  ignores it — historical mistake, decide whether to untrack during the commit.
- App serves the SPA from `frontend/dist` (built with `npm run build`).
- Live capture API already exists: `/api/live/interfaces`, `/api/live/start`
  (body: `{ interface, window_size?, step_size?, forecast_horizon? }`),
  `/api/live/stop`, `/api/live/status`, `/api/live/events` (SSE).
- Detection is feature-driven (entropy dispersion, TCP handshake asymmetry, graph
  fan-out, MITRE stage heuristics) — so real scand / flood / brute-force traffic
  produces real stage detections without needing scenario labels.

## 3. Commit first (staging pending)

Current uncommitted work to commit BEFORE the Attack Lab:
- Frontend page consolidation (16 → 4 pages): `Tabs.tsx`, `AnalysisPage.tsx`,
  `ValidationPage.tsx`, `OperationsPage.tsx`, rewritten `App.tsx`, `Sidebar.tsx`,
  `bare` prop added across `frontend/src/pages/*`.
- Bug fixes: AttackGraphView zoom/pan scroll clamps, Scenarios per-card spinner.
- Sidebar cleanups: renamed "Command Center" → "Dashboard", removed top brand block
  (app icon + "CYBER WORLD / Attack Forecasting Engine"), removed "Defense Sims" tab
  (counterfactual) from the UI entirely.
- `package.json` / `package-lock.json` (vite pinned `^7.3.0`).
- `docs/CODEBASE_SUMMARY.md` (untracked).
- Node modules churn (336 changed `.bin` shims, type changes) — EXCLUDE from commit.

Open decision: also run `git rm -r --cached frontend/node_modules` in this commit to
untrack generated artifacts (matches `.gitignore` intent). Recommended.

## 4. Repo files to create (`scripts/attack_lab/`)

- `setup_lab.sh` — run by the user via `sudo`:
  1. `apt-get install -y hping3 hydra` (+ optional `openssh-server`);
  2. create attacker netns + veth `10.0.0.1 <-> 10.0.0.2` (idempotent);
  3. print verification (e.g. `sudo tshark -i lab-veth0`, `ping 10.0.0.2` from attacker).
- `target_app.py` — the "basic application webserver": tiny Flask app with a login
  form on `10.0.0.2:8080` plus a couple of endpoints. Lightweight; OWASP Juice Shop
  is a heavier alternative if desired.
- Attack wrappers (invoked by the Flask endpoint, run inside `ip netns exec attacker`):
  - `recon.sh`      → `nmap -sS -Pn -p- 10.0.0.2`
  - `bruteforce.sh` → `hydra -l admin -P <small-wordlist> -f 10.0.0.2 http-post-form "/login:user=^USER^&pass=^PASS^:Invalid"` (port 8080), optionally `hydra ssh://10.0.0.2` (22)
  - `synflood.sh` / `synflood.py` → `hping3 -S -p 8080 --flood 10.0.0.2` or a scapy loop
- `README.md` — usage + Oracle Cloud Always Free mirror (below).

## 5. Backend (`netwatch/dashboard/app.py`)

New `/api/lab/*` endpoints, gated by environment flag `NETWATCH_LAB_ENABLED=1`
(demo-only surface — it is a command-executor by design).
- `GET  /api/lab/status`            — lab topology + target app up/down.
- `POST /api/lab/target/start`      — launch `target_app.py` bound to `10.0.0.2:8080`.
- `POST /api/lab/target/stop`       — stop it.
- `POST /api/lab/attack`            — body `{ "attack": "recon"|"bruteforce"|"dos" }`
                                     (whitelist only; no arbitrary strings / shell injection).
- `POST /api/lab/attack/stop`       — terminate the running attack subprocess tree.
- `GET  /api/lab/events`            — small in-memory log of launched attacks + exit output.

Run commands via `subprocess` as `ip netns exec attacker <script>`, stream stdout
to a bounded ring buffer. The Attack Lab tab polls `/api/lab/status` + `/api/lab/events`.

Frontend API client (`frontend/src/services/api.ts`): add `lab*` functions + types.

## 6. Frontend — "Attack Lab" tab

- Third tab on `/` Command Center: id `attacks`, label "Attack Lab", sidebar pill.
  (`frontend/src/pages/CommandCenter.tsx` + `Sidebar.tsx` tabs list; add a new
  `pages/AttackLab.tsx`.)
- Contents:
  - Lab status + interface picker + **Start / Stop Live capture** (reuse `/api/live/*`).
  - Target-app toggle (start/stop) + "open app" link to `http://10.0.0.2:8080`.
  - Attack buttons: **Recon**, **Brute Force**, **DoS** with running state + Stop.
  - Recent events feed / last capture status (reuse SSE from `/api/live/events`).
- Intended flow: start Live capture on `lab-veth0` in the Live tab, then go to
  Attack Lab, fire scripts, watch Overview / Forecast / Attack Graph update live.

## 7. Build, deploy, verify

1. `cd frontend && npm run build` → confirmed new asset hash served (`curl :5040/`).
2. User runs `sudo bash scripts/attack_lab/setup_lab.sh` (enters password once).
3. Restart the server as root on 5040:
   `pkill -f "[r]un.py --port 5040"` then
   `sudo setsid venv/bin/python run.py --port 5040 < /dev/null > /tmp/opencode/netwatch.log 2>&1 &`
   (or your usual root launch). Pipeline prewarm rebuild happens on first request
   (~minutes) after the restart.
4. Smoke test: start live capture on `lab-veth0` → fire Recon (PortScan feature
   spike) → Brute Force (repeated-auth stage) → SYN flood (TCP-asymmetry/entropy alert).
5. Verify with `sudo tshark -i lab-veth0` showing the raw caught packets.

## 8. Online mirror (later, $0)

- Oracle Cloud **Always Free** ARM Ampere VM (4 OCPU / 24 GB) — root native, no setcap
  dance, comfortably runs torch. Replicate the same stack (apt install tshark +
  nmap/hping3/hydra, scapy, build frontend, run server root).
- Attack traffic targets the VM itself (`lab-veth0` or VM IP); open TCP 5040 in the
  security list or wrap in a free Cloudflare tunnel for an https URL.
- AWS t2.micro / Google e2-micro are free-tier alternatives but ARM Oracle fits best.
- Only paid path would be a ~$4–6/mo VPS (e.g. Hetzner/RackNerd) — not needed.

## 9. Troubleshooting notes

- `ip netns exec attacker ...` fails as non-root → server must be root (see §1).
- Capture interface does not appear in `/api/live/interfaces` until the veth is UP —
  `setup_lab.sh` brings both ends up.
- `hydra` http-post-form target must match `target_app.py`'s form field names and
  failure string exactly; keep a tiny bundled wordlist for the demo.
- After server restart the warm pipeline is dropped; first analysis request retrains
  (allow a couple of minutes, watch `/tmp/opencode/netwatch.log`).

## 10. Refs

- Live capture endpoints: `netwatch/dashboard/app.py` (`/api/live/*`).
- Live UI: `frontend/src/pages/LiveMonitor.tsx`.
- Home tabs: `frontend/src/pages/CommandCenter.tsx`.
- Detection engine: `netwatch/forecasting/ensemble_scorer.py`,
  `netwatch/forecasting/stage_predictor.py`, `netwatch/mitre/attack_mapper.py`.