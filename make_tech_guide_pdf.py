"""Generate docs/TECHNICAL_GUIDE.pdf — comprehensive module & architecture guide for SIH26153 NetWatch."""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "TECHNICAL_GUIDE.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

ACCENT = colors.HexColor("#0ba877")
ACCENT2 = colors.HexColor("#00d4aa")
DARK = colors.HexColor("#0a0e1a")
GREY = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#f4f7fa")
BORDER = colors.HexColor("#d8dee6")
WARN = colors.HexColor("#f59e0b")
DANGER = colors.HexColor("#ef4444")

styles = getSampleStyleSheet()

style_cover_title = ParagraphStyle("CoverTitle", parent=styles["Title"], fontSize=28, leading=34, textColor=DARK, alignment=TA_CENTER)
style_cover_sub = ParagraphStyle("CoverSub", parent=styles["Normal"], fontSize=14, leading=20, textColor=GREY, alignment=TA_CENTER)
style_h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, leading=24, textColor=DARK, spaceAfter=8, spaceBefore=6)
style_h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=17, textColor=ACCENT, spaceBefore=10, spaceAfter=6)
style_h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, leading=15, textColor=ACCENT2, spaceBefore=6, spaceAfter=4)
style_body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=15, textColor=colors.HexColor("#2b313a"), spaceAfter=5)
style_code = ParagraphStyle("Code", parent=styles["Code"], fontSize=8.5, leading=13, backColor=LIGHT, borderColor=BORDER, borderWidth=0.8, borderPadding=6, spaceAfter=8, fontName="Courier")
style_bullet = ParagraphStyle("Bullet", parent=style_body, spaceAfter=2, leftIndent=14, bulletIndent=6)
style_cell = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#2b313a"))
style_cell_head = ParagraphStyle("CellHead", parent=style_cell, fontName="Helvetica-Bold", textColor=colors.white)
style_note = ParagraphStyle("Note", parent=style_body, backColor=colors.HexColor("#fffbeb"), borderColor=WARN, borderWidth=0.8, borderPadding=8, spaceAfter=8)
style_warn = ParagraphStyle("Warn", parent=style_body, backColor=colors.HexColor("#fef2f2"), borderColor=DANGER, borderWidth=0.8, borderPadding=8, spaceAfter=8)

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas.drawString(15 * mm, 10 * mm, "SIH26153 — NetWatch · Technical Guide")
    canvas.restoreState()

story = []

# ── Cover ──────────────────────────────────────────────────────
story.append(Spacer(1, 55 * mm))
story.append(Paragraph("SIH26153", style_cover_sub))
story.append(Spacer(1, 4 * mm))
story.append(Paragraph("NetWatch — Technical Architecture & Operations Guide", style_cover_title))
story.append(Spacer(1, 8 * mm))
story.append(Paragraph(
    "AI-Based Network Attack Forecasting from Network Traffic Data<br/>"
    "Counterfactual Cyber World Model · Problem Owner: NTRO",
    style_cover_sub,
))
story.append(Spacer(1, 25 * mm))
story.append(HRFlowable(width="60%", thickness=1.2, color=ACCENT, hAlign="CENTER"))
story.append(Spacer(1, 10 * mm))
story.append(Paragraph(
    "Complete reference: module internals, TShark integration, live capture pipeline, "
    "URL destination monitoring, dashboard navigation, and end-to-end runbook.",
    style_cover_sub,
))
story.append(PageBreak())

# ── 1. System Architecture ─────────────────────────────────────
story.append(Paragraph("1. System Architecture", style_h1))
story.append(Paragraph(
    "NetWatch is an offline, AI-driven network attack forecasting platform. It ingests "
    "network traffic (PCAP/PCAPNG, CSV, JSONL), builds per-window network states, and "
    "uses a trained LSTM World Model plus an ensemble of detection engines to forecast "
    "attack stages. A counterfactual simulator evaluates defensive actions and recommends "
    "the one that minimises future risk. All computation runs locally — no cloud inference.",
    style_body,
))
story.append(Spacer(1, 3 * mm))

# Architecture diagram as text table
arch_data = [
    [Paragraph("<b>Layer</b>", style_cell_head), Paragraph("<b>Components</b>", style_cell_head), Paragraph("<b>Responsibility</b>", style_cell_head)],
    [Paragraph("Ingestion", style_cell), Paragraph("PCAP/CSV/JSONL parsers, ZIP inspector", style_cell), Paragraph("Normalize traffic → feature windows → network states", style_cell)],
    [Paragraph("State Builder", style_cell), Paragraph("netwatch/stage_classifier.py, state_manager.py", style_cell), Paragraph("Sliding windows, host/flow aggregation, MITRE stage labeling", style_cell)],
    [Paragraph("World Model", style_cell), Paragraph("LSTM (PyTorch), scaler, ensemble baselines (ISO/LOF/OC-SVM)", style_cell), Paragraph("Next-window risk + stage probability forecast", style_cell)],
    [Paragraph("Ensemble", style_cell), Paragraph("netwatch/ensemble.py (logreg, rf, gb, mlp)", style_cell), Paragraph("Consensus detection across ML engines", style_cell)],
    [Paragraph("Counterfactual", style_cell), Paragraph("netwatch/counterfactual.py (graph sim + action scorer)", style_cell), Paragraph("What-if simulation, action recommendation", style_cell)],
    [Paragraph("Explainability", style_cell), Paragraph("SHAP (TreeSHAP / DeepSHAP)", style_cell), Paragraph("Feature attributions for risk predictions", style_cell)],
    [Paragraph("Live Capture", style_cell), Paragraph("netwatch/live/ — manager, pipeline, url_monitor, url_target", style_cell), Paragraph("TShark-driven real-time capture & URL filtering", style_cell)],
    [Paragraph("Dashboard", style_cell), Paragraph("Flask + React (Vite), SSE for live updates", style_cell), Paragraph("Visualization, model mgmt, traffic upload, live monitor", style_cell)],
]
tbl = Table(arch_data, colWidths=[30*mm, 50*mm, 90*mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), DARK),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
]))
story.append(tbl)
story.append(Spacer(1, 6 * mm))

# ── 2. Module Reference ────────────────────────────────────────
story.append(Paragraph("2. Module Reference (netwatch/)", style_h1))

modules = [
    ("api/main.py", "Flask application factory. Registers all blueprints: upload, dashboard, models, live, forecast, graph, mitre, explainability, counterfactual, evaluation, scenarios, test_center, system, report. Serves React build from <code>frontend/dist</code> in production."),
    ("api/upload.py", "Handles traffic ingestion (PCAP/PCAPNG/CSV/JSONL/ZIP). Validates, extracts, runs pipeline, stores session artifacts in <code>data/data/sessions/<id>/</code>. Returns session metadata for dashboard."),
    ("api/dashboard.py", "Dashboard overview endpoints: current risk, stage, forecast summary, topology, ensemble scores, recommendations."),
    ("api/models.py", "Model management: upload <code>netwatch_trained_models.zip</code>, list artifacts, reload pipeline, health check."),
    ("api/live.py", "Legacy live monitor (interface-only). <code>/api/live/start</code>, <code>/status</code>, <code>/stop</code>, <code>/events</code> (SSE). Captures all traffic on an interface."),
    ("api/forecast.py", "Forecast radar & projection endpoints. Returns future risk timeline, stage probabilities, confidence bands."),
    ("api/graph.py", "Attack graph: current + predicted nodes/edges, stage transitions."),
    ("api/mitre.py", "MITRE ATT&CK trajectory mapping. Stage → technique mapping, kill-chain progression."),
    ("api/explainability.py", "SHAP explanations: global feature importance, per-prediction waterfall."),
    ("api/counterfactual.py", "What-if simulation: enumerate defensive actions, simulate graph, score risk reduction, return recommended action."),
    ("api/evaluation.py", "Model evaluation: world model vs baselines (ISO/LOF/OC-SVM/LogReg/RF/GB/MLP) on holdout data."),
    ("api/scenarios.py", "Ad-hoc scenario runner: inject custom traffic, run pipeline, inspect results."),
    ("api/test_center.py", "Model test center: validation checks, data quality, drift detection."),
    ("api/system.py", "System health: TShark availability, disk, memory, pipeline status."),
    ("api/report.py", "Export session report (JSON/PDF)."),
    ("pipeline.py", "Core orchestrator: <code>run_pipeline()</code> — ingest → build states → forecast → ensemble → counterfactual → explainability. Returns <code>PipelineResult</code>."),
    ("stage_classifier.py", "Heuristic + ML stage classifier. Maps feature windows → MITRE stages (RECON, INITIAL_ACCESS, EXECUTION, PERSISTENCE, PRIVILEGE_ESCALATION, DEFENSE_EVASION, CREDENTIAL_ACCESS, DISCOVERY, LATERAL_MOVEMENT, COLLECTION, COMMAND_AND_CONTROL, EXFILTRATION, IMPACT)."),
    ("state_manager.py", "Manages network state windows: host/flow aggregation, feature extraction, sliding window logic."),
    ("ensemble.py", "Ensemble detector: trains logistic regression, random forest, gradient boosting, MLP on labeled windows. Produces consensus score."),
    ("counterfactual.py", "Graph-based counterfactual simulator. Actions: BLOCK_IP, ISOLATE_HOST, RATE_LIMIT, PATCH_VULN, DEPLOY_HONEYPOT, UPDATE_RULES. Simulates edge removal/addition, scores risk delta."),
    ("world_model.py", "LSTM World Model (PyTorch). Sequence → next-window risk + stage distribution. Trained in Colab, loaded at runtime."),
    ("features.py", "Feature engineering: statistical, temporal, graph, protocol, entropy features per window."),
    ("data_loader.py", "PCAP/CSV/JSONL loaders. Uses scapy (optional) for PCAP; pandas for CSV/JSONL."),
    ("live/manager.py", "Live session lifecycle: start/stop/status/history. Tracks TShark processes, sensor metadata, world_model_status."),
    ("live/live_state.py", "In-memory live state: host tracks, flow tracks, timeline events, URL telemetry, metrics history. Thread-safe with locks."),
    ("live/event_parser.py", "TShark JSON parser. Extracts IP/TCP/UDP/TLS/DNS fields, computes IAT, packet sizes, flags, handshakes. Emits structured events."),
    ("live/live_pipeline.py", "Real-time feature builder. Consumes parsed events → updates host/flow tracks → computes window features → calls world_model/ensemble → publishes SSE events (network_state, risk, forecast, stage, graph, mitre, explainability, counterfactual)."),
    ("live/url_target.py", "<b>NEW</b> URL resolution & tracking. <code>UrlResolver.resolve()</code> → A/AAAA records, ports, scheme, path. <code>UrlTargetTracker</code> maintains IP history, resolution count, change detection."),
    ("live/url_monitor.py", "<b>NEW</b> Destination-observed capture. Builds TShark display filter for resolved IPs + ports. Spawns TShark with <code>-Y</code> filter, pipes JSON to event_parser. Handles HTTPS (TLS-only visibility) and DNS change re-resolution."),
    ("live/config.py", "Live capture configuration dataclasses: <code>LiveConfig</code> (interface, window/step size, forecast horizon), <code>UrlMonitorConfig</code> (url, interface, resolver settings)."),
]

for mod, desc in modules:
    story.append(Paragraph(f"<code>{mod}</code>", style_h3))
    story.append(Paragraph(desc, style_body))
    story.append(Spacer(1, 2 * mm))

story.append(PageBreak())

# ── 3. TShark Integration ──────────────────────────────────────
story.append(Paragraph("3. TShark Integration — Deep Dive", style_h1))
story.append(Paragraph(
    "TShark (Wireshark CLI) is the packet capture engine. NetWatch uses it in two modes:",
    style_body,
))
story.append(ListFlowable([
    ListItem(Paragraph("<b>Interface Mode (legacy)</b>: Captures ALL traffic on an interface. Filter: none (or optional BPF).", style_bullet)),
    ListItem(Paragraph("<b>URL Monitor Mode (new)</b>: Captures ONLY traffic to/from resolved target IPs/ports. Filter: dynamic display filter built from <code>UrlTargetTracker</code>.", style_bullet)),
], bulletType="bullet", start="•"))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("3.1 TShark Command Construction", style_h2))
story.append(Paragraph(
    "In <code>netwatch/live/url_monitor.py</code>, <code>UrlMonitor._build_tshark_cmd()</code> constructs:",
    style_body,
))
story.append(Paragraph(
    "<code>tshark -i <interface> -T json -Y \"<display_filter>\" -l</code>",
    style_code,
))
story.append(Paragraph("Where <code><display_filter></code> is built as:", style_body))
story.append(Paragraph(
    "<code>(ip.addr == 1.2.3.4 || ip.addr == 5.6.7.8) && (tcp.port == 443 || tcp.port == 80 || udp.port == 443 || udp.port == 80)</code>",
    style_code,
))
story.append(Paragraph(
    "• <code>-i</code> = interface name (e.g., <code>Ethernet</code>, <code>Wi-Fi</code>, <code>eth0</code>)<br/>"
    "• <code>-T json</code> = output each packet as JSON (one line per packet)<br/>"
    "• <code>-Y</code> = display filter (applied after capture, more expressive than BPF)<br/>"
    "• <code>-l</code> = line-buffered stdout (critical for real-time streaming)<br/>"
    "• <code>-n</code> = no name resolution (speed)<br/>"
    "• <code>-Q</code> = quiet (suppress packet count on stderr)",
    style_body,
))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("3.2 JSON Output Parsing", style_h2))
story.append(Paragraph(
    "Each TShark JSON line contains <code>_source.layers</code> with protocols: frame, eth, ip, tcp, udp, tls, dns, http, etc. "
    "<code>event_parser.py</code> extracts:",
    style_body,
))
story.append(ListFlowable([
    ListItem(Paragraph("5-tuple: src_ip, dst_ip, src_port, dst_port, protocol", style_bullet)),
    ListItem(Paragraph("Timestamps: <code>frame.time_epoch</code> (float seconds)", style_bullet)),
    ListItem(Paragraph("Lengths: <code>frame.len</code>, <code>ip.len</code>, TCP payload size", style_bullet)),
    ListItem(Paragraph("TCP flags: SYN, SYN-ACK, ACK, RST, FIN, PSH, URG", style_bullet)),
    ListItem(Paragraph("TLS: handshake type (Client Hello, Server Hello, Certificate, Finished)", style_bullet)),
    ListItem(Paragraph("DNS: query name, response IPs (A/AAAA)", style_bullet)),
], bulletType="bullet", start="•"))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("3.3 Event Emission", style_h2))
story.append(Paragraph(
    "Parsed packets are grouped into flows (5-tuple). For each flow, the parser emits granular events "
    "to <code>LiveState</code>:",
    style_body,
))
events_data = [
    [Paragraph("<b>Event Type</b>", style_cell_head), Paragraph("<b>Trigger</b>", style_cell_head), Paragraph("<b>Payload</b>", style_cell_head)],
    [Paragraph("dns", style_cell), Paragraph("DNS query/response for target hostname", style_cell), Paragraph("hostname, resolved_ips, query_type", style_cell)],
    [Paragraph("connection", style_cell), Paragraph("TCP SYN (pure) to target IP:port", style_cell), Paragraph("flow_id, direction, flags", style_cell)],
    [Paragraph("traffic", style_cell), Paragraph("Any packet matching target filter", style_cell), Paragraph("bytes, flags, payload_len, tls_info", style_cell)],
    [Paragraph("flow", style_cell), Paragraph("New 5-tuple flow created", style_cell), Paragraph("flow_id, protocol, endpoints", style_cell)],
    [Paragraph("network_state", style_cell), Paragraph("Every window step (default 5s)", style_cell), Paragraph("features dict, timestamp", style_cell)],
    [Paragraph("risk", style_cell), Paragraph("World model inference", style_cell), Paragraph("current_risk, confidence", style_cell)],
    [Paragraph("forecast", style_cell), Paragraph("World model forecast", style_cell), Paragraph("future_risk[], stage_probs[]", style_cell)],
    [Paragraph("stage", style_cell), Paragraph("Stage classifier output", style_cell), Paragraph("stage, probability", style_cell)],
]
tbl = Table(events_data, colWidths=[30*mm, 60*mm, 80*mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), DARK),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tbl)
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("3.4 TShark Requirements & Troubleshooting", style_h2))
story.append(ListFlowable([
    ListItem(Paragraph("<b>Install</b>: Wireshark (includes TShark). On Windows: <code>winget install WiresharkFoundation.Wireshark</code>. On Linux: <code>apt install tshark</code> / <code>dnf install wireshark-cli</code>.", style_bullet)),
    ListItem(Paragraph("<b>Path</b>: NetWatch auto-detects <code>tshark</code> on PATH. Override with env <code>NETWATCH_TSHARK_PATH</code>.", style_bullet)),
    ListItem(Paragraph("<b>Permissions</b>: Capture requires admin/root or <code>setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap</code> (Linux). Windows: run as Administrator or grant 'Capture' privilege.", style_bullet)),
    ListItem(Paragraph("<b>Version</b>: Tested with TShark 3.x–4.x. JSON output format stable across versions.", style_bullet)),
    ListItem(Paragraph("<b>No TShark?</b> Dashboard shows warning; live features disabled. Offline PCAP analysis still works.", style_bullet)),
], bulletType="bullet", start="•"))
story.append(PageBreak())

# ── 4. URL Monitor (Destination-Observed Capture) ──────────────
story.append(Paragraph("4. URL Monitor — Destination-Observed Live Capture", style_h1))
story.append(Paragraph(
    "The URL Monitor resolves a URL (e.g., <code>https://api.example.com/v1/data</code>) to its "
    "destination infrastructure and observes ONLY the local network transmission to/from those "
    "resolved endpoints. This is a <b>network monitor</b>, not a web scraper.",
    style_body,
))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("4.1 Flow: Start → Resolve → Capture → Analyze", style_h2))
steps = [
    ("1. User Input", "Enter URL + select interface on <b>/url-monitor</b> page."),
    ("2. Validate", "Client-side URL parse; backend re-validates."),
    ("3. Resolve DNS", "<code>UrlResolver.resolve()</code> → A/AAAA records, scheme, port, path. Cached with TTL."),
    ("4. Build Filter", "<code>UrlMonitor._build_display_filter()</code> creates TShark <code>-Y</code> filter for all resolved IPs + ports."),
    ("5. Spawn TShark", "Subprocess with line-buffered JSON output. Stdout → parser thread."),
    ("6. Parse & Track", "<code>event_parser</code> extracts packets → <code>LiveState</code> updates host/flow tracks, URL telemetry."),
    ("7. Real-time Features", "<code>live_pipeline</code> computes window features → World Model + Ensemble → SSE events."),
    ("8. DNS Re-check", "Periodic re-resolution (configurable). On IP change: filter rebuilt, TShark restarted seamlessly."),
    ("9. Stop", "User clicks STOP or API <code>/api/live/url/stop</code> → TShark terminated, session archived."),
]
for title, desc in steps:
    story.append(Paragraph(f"<b>{title}</b>: {desc}", style_bullet))
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("4.2 API Endpoints", style_h2))
api_data = [
    [Paragraph("Method + Path", style_cell_head), Paragraph("Request Body", style_cell_head), Paragraph("Response", style_cell_head)],
    [Paragraph("<code>POST /api/live/url/start</code>", style_cell), Paragraph("<code>{url, interface, window_size?, step_size?, forecast_horizon?}</code>", style_cell), Paragraph("<code>{analysis_id, mode, status, target, sensor}</code>", style_cell)],
    [Paragraph("<code>GET /api/live/url/status/<id></code>", style_cell), Paragraph("—", style_cell), Paragraph("Full status: source, target, traffic, url_metrics, timeline, network_state, risk, forecast, stage, graph, mitre, explainability, counterfactual, ensemble", style_cell)],
    [Paragraph("<code>POST /api/live/url/stop</code>", style_cell), Paragraph("<code>{analysis_id?}</code>", style_cell), Paragraph("<code>{status, analysis_id, mode, sensor_stats}</code>", style_cell)],
    [Paragraph("<code>GET /api/live/events</code>", style_cell), Paragraph("SSE", style_cell), Paragraph("Event streams: update, url_status, dns, connection, traffic, flow, network_state, risk, forecast, stage, graph, mitre, explainability, counterfactual, stopped", style_cell)],
]
tbl = Table(api_data, colWidths=[50*mm, 50*mm, 70*mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), DARK),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tbl)
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("4.3 HTTPS / TLS Limitations", style_h2))
story.append(Paragraph(
    "• <b>Encrypted payload</b>: TLS 1.2/1.3 encrypts application data. NetWatch sees only metadata: handshake, record lengths, timing.<br/>"
    "• <b>SNI</b>: Client Hello may reveal hostname (if not encrypted via ECH).<br/>"
    "• <b>No MITM</b>: NetWatch does NOT perform TLS interception, certificate injection, or key logging.<br/>"
    "• <b>What you get</b>: Connection counts, handshake success/failure, byte/packet rates, retransmissions, RSTs, IAT, packet sizes, flow duration — all from observable wire data.",
    style_body,
))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("4.4 DNS Change Handling", style_h2))
story.append(Paragraph(
    "<code>UrlTargetTracker</code> stores <code>ip_history: List[{resolved_at, ips}]</code>. On each re-resolution: "
    "if new IPs differ from previous, <code>target_ip_changes</code> increments, filter rebuilt, TShark restarted. "
    "Dashboard shows <b>TARGET IPs UPDATED</b> banner with before/after counts.",
    style_body,
))
story.append(PageBreak())

# ── 5. Live Dashboard & URL Monitor UI ─────────────────────────
story.append(Paragraph("5. Live Dashboard & URL Monitor UI", style_h1))

story.append(Paragraph("5.1 Accessing the Dashboards", style_h2))
story.append(Paragraph(
    "After starting the server (<code>python run.py</code>), open <b>http://localhost:5000</b>.<br/>"
    "• <b>Legacy Live Monitor</b>: Sidebar → <b>Live Monitor</b> (<code>/live</code>) — captures all interface traffic.<br/>"
    "• <b>URL Monitor</b>: Sidebar → <b>URL Monitor</b> (<code>/url-monitor</code>) — destination-observed capture.",
    style_body,
))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("5.2 URL Monitor Page Walkthrough", style_h2))
ui_sections = [
    ("Header", "Mode label 'URL Transmission Monitor', START/STOP button. START validates TShark availability."),
    ("Config Card", "URL input (must include scheme), Interface dropdown (auto-populated from <code>/api/live/interfaces</code>), Mode badge (URL MONITOR). TShark status dot + version."),
    ("Target Card", "Resolved destination: URL, hostname, scheme, port, resolved IP count. Capture/TShark status pills."),
    ("Monitoring Scope Card", "Explicit notice: monitoring source interface, target hostname, HTTPS limitation note (if HTTPS), DNS change indicator."),
    ("Real-time Metrics (8 cards)", "Upload/Download rate, Packets, Bytes, Active flows, TCP connections (SYN/TLS), RST/Retransmissions, Network states (world model readiness)."),
    ("Rate Chart", "SVG sparkline: Packets/sec (green) + Bytes/sec (teal). Range selector: 30s / 60s / 5m. Updates via SSE + 2.5s polling."),
    ("No-Traffic State", "When <code>traffic.packets == 0</code>: 'Monitoring active. No matching traffic observed yet.'"),
    ("Network Behavior Table", "Packet rate, Byte rate, IAT mean/variance, Avg packet size/variance, TCP handshake SYN/SYN-ACK, RST count, Retransmissions, TLS handshakes, Destination IPs observed, DNS resolutions."),
    ("AI Forecast Panel", "Current risk %, Future max risk %, Trend, Confidence, Risk gauge bar. Predicted future state t+1..t+5 (risk %, stage, color-coded). Shows 'INSUFFICIENT DATA' until world model warms up."),
    ("Live Timeline", "Reverse-chronological events from SSE: dns (blue), connection/traffic (green), flow (teal), risk (amber), forecast (red). Colored dots, timestamp, type, message."),
    ("Resolved IPs Panel", "Pill badges for each resolved IP. Updates live on DNS change."),
]
for title, desc in ui_sections:
    story.append(Paragraph(f"<b>{title}</b>: {desc}", style_bullet))
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("5.3 Live Events (SSE) Channel Reference", style_h2))
sse_data = [
    [Paragraph("Event", style_cell_head), Paragraph("Frequency", style_cell_head), Paragraph("Content", style_cell_head)],
    [Paragraph("update", style_cell), Paragraph("~1-5s (batch)", style_cell), Paragraph("Full status dict: source, target, traffic, url_metrics, timeline[]", style_cell)],
    [Paragraph("url_status", style_cell), Paragraph("Per packet batch", style_cell), Paragraph("traffic, url_metrics delta", style_cell)],
    [Paragraph("dns", style_cell), Paragraph("On resolution", style_cell), Paragraph("hostname, ips, query_type", style_cell)],
    [Paragraph("connection", style_cell), Paragraph("On TCP SYN", style_cell), Paragraph("flow_id, direction, flags", style_cell)],
    [Paragraph("traffic", style_cell), Paragraph("Per packet", style_cell), Paragraph("bytes, flags, tls, payload", style_cell)],
    [Paragraph("flow", style_cell), Paragraph("New flow", style_cell), Paragraph("flow_id, protocol, endpoints", style_cell)],
    [Paragraph("network_state", style_cell), Paragraph("Every window step", style_cell), Paragraph("features{}, timestamp", style_cell)],
    [Paragraph("risk", style_cell), Paragraph("On inference", style_cell), Paragraph("current_risk, confidence", style_cell)],
    [Paragraph("forecast", style_cell), Paragraph("On forecast", style_cell), Paragraph("future[], horizon", style_cell)],
    [Paragraph("stage", style_cell), Paragraph("On classification", style_cell), Paragraph("stage, probability", style_cell)],
    [Paragraph("graph/mitre/explainability/counterfactual", style_cell), Paragraph("On computation", style_cell), Paragraph("Full objects", style_cell)],
    [Paragraph("stopped", style_cell), Paragraph("On stop", style_cell), Paragraph("{analysis_id, reason}", style_cell)],
]
tbl = Table(sse_data, colWidths=[35*mm, 30*mm, 105*mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), DARK),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tbl)
story.append(PageBreak())

# ── 6. Frontend Architecture ───────────────────────────────────
story.append(Paragraph("6. Frontend Architecture (React + Vite)", style_h1))

story.append(Paragraph("6.1 Project Structure", style_h2))
story.append(Paragraph(
    "<code>frontend/src/</code>",
    style_code,
))
story.append(Paragraph(
    "components/ui/ — primitives (Card, Grid, Dot, Pill, Bar, MetricCard, Button, etc.)<br/>"
    "components/layout/ — Layout, Sidebar, TopBar<br/>"
    "pages/ — one file per route (Overview, AnalyzePCAP, LiveMonitor, <b>UrlMonitor</b>, NetworkState, Forecast, AttackGraph, Mitre, Explainability, CounterfactualLab, ModelTestCenter, Evaluation, Scenarios, History, ReportExport, System)<br/>"
    "services/api.ts — typed fetch wrappers for all API endpoints<br/>"
    "types/index.ts — shared TypeScript interfaces<br/>"
    "styles/theme.ts — palette, gauges, stage colors<br/>"
    "App.tsx — routes + lazy loading<br/>"
    "main.tsx — entry point",
    style_body,
))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("6.2 Key Patterns", style_h2))
story.append(ListFlowable([
    ListItem(Paragraph("<b>Lazy routes</b>: <code>const Page = lazy(() => import('./pages/Page'))</code> — code splitting.", style_bullet)),
    ListItem(Paragraph("<b>SSE hook pattern</b>: <code>EventSource</code> in <code>useEffect</code>, addEventListener per event type, cleanup on unmount.", style_bullet)),
    ListItem(Paragraph("<b>Polling fallback</b>: 2.5s interval for full status (risk/forecast/graph) when SSE drops.", style_bullet)),
    ListItem(Paragraph("<b>State accumulation</b>: Client-side sample buffer (max 4000 points) for charts, filtered by range selector.", style_bullet)),
    ListItem(Paragraph("<b>Type safety</b>: Strict TS, <code>Record<string, unknown></code> over <code>any</code>, discriminated unions for events.", style_bullet)),
    ListItem(Paragraph("<b>Theming</b>: Central <code>palette</code> object, CSS variables not used — inline styles for portability.", style_bullet)),
], bulletType="bullet", start="•"))
story.append(PageBreak())

# ── 7. End-to-End Runbook ──────────────────────────────────────
story.append(Paragraph("7. End-to-End Runbook", style_h1))

story.append(Paragraph("7.1 Full Stack Startup (Development)", style_h2))
story.append(Paragraph("<b>Terminal 1 — Backend:</b>", style_body))
story.append(Paragraph(
    "cd C:\\sih 2026\\external_hackathon\n"
    "venv\\Scripts\\activate\n"
    "python run.py",
    style_code,
))
story.append(Paragraph("→ Serves on <b>http://localhost:5000</b> (API + React build if exists)", style_body))
story.append(Spacer(1, 3 * mm))
story.append(Paragraph("<b>Terminal 2 — Frontend Dev Server (hot reload):</b>", style_body))
story.append(Paragraph(
    "cd C:\\sih 2026\\external_hackathon\\frontend\n"
    "npm run dev",
    style_code,
))
story.append(Paragraph("→ Serves on <b>http://localhost:5173</b> (proxies API to :5000 via Vite proxy)", style_body))
story.append(Spacer(1, 3 * mm))
story.append(Paragraph(
    "Open <b>http://localhost:5173</b> for development (hot reload). "
    "Open <b>http://localhost:5000</b> for production-like (served by Flask).",
    style_note,
))
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("7.2 Production Build", style_h2))
story.append(Paragraph(
    "cd frontend\n"
    "npm run build\n"
    "cd ..\n"
    "python run.py",
    style_code,
))
story.append(Paragraph(
    "Flask serves <code>frontend/dist/index.html</code> and <code>/assets/*</code> at <code>http://localhost:5000</code>.",
    style_body,
))
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("7.3 Docker (Optional)", style_h2))
story.append(Paragraph(
    "docker-compose up --build\n"
    "→ Services: web (Flask+React on :5000), optional redis/postgres if configured.",
    style_code,
))
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("7.4 Complete Workflow: URL Monitor Live Capture", style_h2))
workflow = [
    ("1. Prerequisites", "TShark installed & on PATH (or NETWATCH_TSHARK_PATH set). Admin/root for capture."),
    ("2. Start Backend", "<code>python run.py</code> → <code>http://localhost:5000</code>"),
    ("3. Open URL Monitor", "Sidebar → URL Monitor (<code>/url-monitor</code>)"),
    ("4. Configure", "Enter URL (e.g., <code>https://httpbin.org/get</code>), pick interface (must be UP, not loopback)."),
    ("5. Start", "Click <b>START URL MONITOR</b>. Backend resolves DNS, builds filter, spawns TShark."),
    ("6. Observe", "Real-time metrics appear. Rate chart draws. Timeline populates. Risk/forecast update every window."),
    ("7. Generate Traffic", "From another terminal: <code>curl https://httpbin.org/get</code> or browse the URL."),
    ("8. Verify", "Packets > 0, flows > 0, upload/download rates > 0, TLS handshakes counted."),
    ("9. Stop", "Click <b>STOP</b>. Session ends. Data retained in live state for review."),
    ("10. Export", "Use <b>Report Export</b> page (/report) to download session JSON/PDF."),
]
for title, desc in workflow:
    story.append(Paragraph(f"<b>{title}</b>: {desc}", style_bullet))
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("7.5 Complete Workflow: Offline PCAP Analysis", style_h2))
workflow2 = [
    ("1. Start Backend", "<code>python run.py</code>"),
    ("2. Upload Traffic", "Dashboard → Upload page → drop PCAP/CSV/JSONL/ZIP"),
    ("3. Auto-Pipeline", "Ingestion triggers full pipeline: states → forecast → ensemble → counterfactual → explainability"),
    ("4. Explore", "Navigate Dashboard, Topology, Forecast Radar, Attack Graph, Counterfactual, MITRE, Explainability, Ensemble, Evaluation"),
    ("5. Upload Models", "Models page → drop <code>netwatch_trained_models.zip</code> (from Colab) for real weights"),
    ("6. Export Report", "Report Export page → download PDF/JSON"),
]
for title, desc in workflow2:
    story.append(Paragraph(f"<b>{title}</b>: {desc}", style_bullet))
story.append(PageBreak())

# ── 8. Data Flow Summary ───────────────────────────────────────
story.append(Paragraph("8. End-to-End Data Flow", style_h1))

story.append(Paragraph("8.1 Offline Ingestion Pipeline", style_h2))
offline_flow = [
    "PCAP/CSV/JSONL/ZIP → api/upload.py",
    "→ data_loader.py (parse → DataFrame)",
    "→ features.py (extract window features)",
    "→ state_manager.py (build NetworkState windows)",
    "→ stage_classifier.py (label MITRE stages)",
    "→ world_model.py (LSTM forecast risk + stage probs)",
    "→ ensemble.py (consensus detection score)",
    "→ counterfactual.py (simulate actions → recommend)",
    "→ explainability.py (SHAP attributions)",
    "→ PipelineResult persisted to data/data/sessions/<id>/",
    "→ Dashboard pages read session artifacts",
]
for i, step in enumerate(offline_flow, 1):
    story.append(Paragraph(f"{i}. {step}", style_bullet))
story.append(Spacer(1, 4 * mm))

story.append(Paragraph("8.2 Live URL Monitor Pipeline", style_h2))
live_flow = [
    "User: URL + Interface → POST /api/live/url/start",
    "url_target.py: resolve() → IPs, ports, scheme, path",
    "url_monitor.py: build display filter → spawn TShark -Y filter -T json -l",
    "event_parser.py: parse JSON → emit dns/connection/traffic/flow events",
    "live_state.py: update host_tracks, flow_tracks, url_telemetry, timeline",
    "live_pipeline.py: every step_size → compute window features →",
    "  world_model.forward() → risk + forecast",
    "  ensemble.predict() → consensus",
    "  stage_classifier.predict() → stage",
    "  counterfactual.simulate() → recommended action",
    "  explainability.shap() → attributions",
    "  → publish SSE events (network_state, risk, forecast, stage, graph, mitre, explainability, counterfactual)",
    "Frontend: SSE + poll → update metrics, chart, timeline, forecast panel",
]
for i, step in enumerate(live_flow, 1):
    story.append(Paragraph(f"{i}. {step}", style_bullet))
story.append(Spacer(1, 6 * mm))

# ── 9. Configuration Reference ─────────────────────────────────
story.append(Paragraph("9. Configuration Reference", style_h1))

config_data = [
    [Paragraph("Env / Config", style_cell_head), Paragraph("Default", style_cell_head), Paragraph("Description", style_cell_head)],
    [Paragraph("NETWATCH_TSHARK_PATH", style_cell), Paragraph("auto-detect", style_cell), Paragraph("Full path to tshark binary"), style_cell],
    [Paragraph("LIVE_WINDOW_SIZE", style_cell), Paragraph("60", style_cell), Paragraph("Feature window seconds"), style_cell],
    [Paragraph("LIVE_STEP_SIZE", style_cell), Paragraph("5", style_cell), Paragraph("Sliding step seconds"), style_cell],
    [Paragraph("LIVE_FORECAST_HORIZON", style_cell), Paragraph("5", style_cell), Paragraph("Future windows to forecast"), style_cell],
    [Paragraph("URL_RESOLVE_TTL", style_cell), Paragraph("300", style_cell), Paragraph("DNS cache TTL (seconds)"), style_cell],
    [Paragraph("URL_RECHECK_INTERVAL", style_cell), Paragraph("60", style_cell), Paragraph("Periodic re-resolution interval"), style_cell],
    [Paragraph("FLASK_PORT", style_cell), Paragraph("5000", style_cell), Paragraph("Backend port"), style_cell],
    [Paragraph("VITE_API_BASE", style_cell), Paragraph("'' (relative)", style_cell), Paragraph("Frontend API base (dev/prod)"), style_cell],
]
tbl = Table(config_data, colWidths=[50*mm, 30*mm, 90*mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), DARK),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tbl)
story.append(PageBreak())

# ── 10. Testing & Validation ───────────────────────────────────
story.append(Paragraph("10. Testing & Validation", style_h1))

story.append(Paragraph("10.1 Backend Tests", style_h2))
story.append(Paragraph(
    "<code>python -m pytest tests/ -q</code>",
    style_code,
))
story.append(Paragraph(
    "Key live tests in <code>tests/test_live.py</code>:",
    style_body,
))
test_list = [
    "test_live_health — TShark detection",
    "test_live_interfaces — interface enumeration",
    "test_live_start_stop_interface_mode — legacy capture lifecycle",
    "test_live_pipeline_interface_mode_emits_events — SSE event emission",
    "test_live_pipeline_url_mode_filters_target_traffic — <b>URL monitor filter correctness</b>",
    "test_live_pipeline_url_mode_dns_recheck — DNS change handling",
    "test_live_pipeline_url_mode_https_limitation — HTTPS metadata-only note",
    "test_live_url_start_invalid_url — validation",
    "test_live_url_start_missing_tshark — graceful degradation",
]
for t in test_list:
    story.append(Paragraph(f"• {t}", style_bullet))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("10.2 Frontend Checks", style_h2))
story.append(Paragraph(
    "<code>cd frontend && npm run build</code> — TypeScript compile + Vite bundle (must pass)<br/>"
    "<code>cd frontend && npm run dev</code> — dev server, open /url-monitor, verify no console errors",
    style_code,
))
story.append(Spacer(1, 3 * mm))

story.append(Paragraph("10.3 Manual Smoke Test Checklist", style_h2))
checks = [
    "✓ Backend starts, <code>GET /api/live/health</code> returns <code>{available: true}</code>",
    "✓ <code>GET /api/live/interfaces</code> returns at least one UP non-loopback interface",
    "✓ URL Monitor page loads, interface dropdown populated",
    "✓ Enter valid HTTPS URL → START → phase becomes 'capturing'",
    "✓ Target card shows resolved IPs (>0), scheme, port",
    "✓ Generate traffic (curl/browser) → packets/bytes > 0 in metrics cards",
    "✓ Rate chart draws lines (packets/sec, bytes/sec)",
    "✓ Timeline shows dns → connection → traffic → flow events",
    "✓ Risk/forecast panel updates (may show 'INSUFFICIENT DATA' until model warms)",
    "✓ STOP button ends capture, phase returns to 'idle'",
    "✓ Re-start works (new analysis_id)",
]
for c in checks:
    story.append(Paragraph(c, style_bullet))
story.append(Spacer(1, 6 * mm))

# ── Footer ─────────────────────────────────────────────────────
story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER))
story.append(Spacer(1, 3 * mm))
story.append(Paragraph(
    "NetWatch · SIH26153 · Counterfactual Cyber World Model — Problem Owner: NTRO.<br/>"
    "Generated from <code>make_tech_guide_pdf.py</code>. For questions, see README.md or repo issues.",
    ParagraphStyle("foot", parent=style_body, textColor=GREY, fontSize=8.5, alignment=TA_LEFT),
))

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=15 * mm, rightMargin=15 * mm,
    topMargin=18 * mm, bottomMargin=16 * mm,
    title="SIH26153 — NetWatch: Technical Architecture & Operations Guide",
    author="SIH26153 Team",
)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("Wrote", OUT)