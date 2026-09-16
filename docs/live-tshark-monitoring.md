# Live TShark Monitoring

Real-time network attack forecasting with **TShark as the ONLY live packet
capture source**. No Zeek, no Suricata, no raw-socket capture — the live
pipeline reads TShark's streaming JSON line output and pushes every parsed
packet through the existing Cyber World Model feature/build/forecast chain.

## Requirements

- Linux host (interface discovery + raw capture; TShark capture is disabled
  on Windows by design)
- `tshark` ≥ v3.0 on the `PATH` (or `NETWATCH_TSHARK_PATH`)
- Elevated privileges for capture: `sudo`, or `CAP_NET_RAW` in Docker

Install TShark:

```bash
sudo apt-get install -y tshark
tshark --version   # verify
```

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

## Configuration

All options live in `configs/config.yaml` under `live:` and can be
overridden by environment variables:

| Env var | Default | Purpose |
| --- | --- | --- |
| `NETWATCH_LIVE_ENABLED` | `1` | Master kill-switch |
| `NETWATCH_TSHARK_PATH` | `tshark` | Path to the tshark binary |
| `NETWATCH_LIVE_TSHARK_FORMAT` | `ek` | Output format (ek is the only supported default) |
| `NETWATCH_LIVE_BPF_FILTER` | *(empty)* | Optional BPF filter, e.g. `"not port 22"` |
| `NETWATCH_LIVE_SNAPLEN` | `65535` | Snapshot length |
| `NETWATCH_LIVE_DEFAULT_INTERFACE` | *(empty)* | Auto-select first usable iface |
| `NETWATCH_LIVE_WINDOW_SIZE` | `30` | Seconds per aggregation window |
| `NETWATCH_LIVE_STEP_SIZE` | `5` | Seconds between window starts |
| `NETWATCH_LIVE_FORECAST_HORIZON` | `5` | K-step rollout |
| `NETWATCH_LIVE_MIN_STATES_FOR_MODEL` | `8` | States before first model fit |
| `NETWATCH_LIVE_MODEL_REFIT_INTERVAL` | `3` | Re-fit the linear model every N windows |

## API endpoints

All behind `/api/live/*`:

- `GET /api/live/health` — TShark availability + version probe
- `GET /api/live/interfaces` — discoverable interfaces
- `POST /api/live/start` — `{ "interface", "window_size", "step_size", "forecast_horizon" }`
- `POST /api/live/stop` — stop the current session
- `GET /api/live/status` — lightweight session status (frontend polls when idle)
- `GET /api/live/events` — **SSE stream** (`text/event-stream`) of live updates
- `GET /api/live/analysis/<id>` — full canonical analysis document
- `GET /api/live/history` — previous session summaries

## Frontend

`/live` route → `LiveMonitor` page (see `frontend/src/pages/LiveMonitor.tsx`):

1. Verify TShark health + pick an interface
2. Start/stop capture
3. Live metrics: packets, flows, hosts, network states, packets/sec
4. Current risk, current stage and window configuration
5. Live event log via SSE (`/api/live/events`)
6. Previous-session history

## Running

Bare metal:

```bash
python run.py            # Flask serves SPA + /api/live/*
# open http://localhost:5000/live
```

Docker (needs raw sockets on the host network):

```bash
docker compose --profile live up live
```

## Security notes

- The TShark command is built from validated arguments only: interface names
  are restricted to `[A-Za-z0-9_.-]`, the BPF filter is an explicit argument
  (no shell interpolation), and `shell=False` is always used.
- Interface names, window sizes, steps and horizons are validated / coerced
  before use.
- Capture requires elevated privileges; do not run the container as root
  outside an isolated network namespace.

## Testing

```bash
python -m pytest tests/test_live.py -q
```