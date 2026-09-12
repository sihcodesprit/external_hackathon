"""Generate docs/HOW_TO_RUN.pdf — step-by-step guide for running SIH26153 NetWatch."""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
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
OUT = os.path.join(ROOT, "docs", "HOW_TO_RUN.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

ACCENT = colors.HexColor("#0ba877")
DARK = colors.HexColor("#0a0e1a")
GREY = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#f4f7fa")
BORDER = colors.HexColor("#d8dee6")

styles = getSampleStyleSheet()

style_cover_title = ParagraphStyle(
    "CoverTitle", parent=styles["Title"], fontSize=30, leading=36,
    textColor=DARK, alignment=TA_CENTER,
)
style_cover_sub = ParagraphStyle(
    "CoverSub", parent=styles["Normal"], fontSize=15, leading=22,
    textColor=GREY, alignment=TA_CENTER,
)
style_h1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontSize=20, leading=26,
    textColor=DARK, spaceAfter=8, spaceBefore=6,
)
style_h2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontSize=14, leading=18,
    textColor=ACCENT, spaceBefore=10, spaceAfter=6,
)
style_body = ParagraphStyle(
    "Body", parent=styles["Normal"], fontSize=10.5, leading=16,
    textColor=colors.HexColor("#2b313a"), spaceAfter=6,
)
style_code = ParagraphStyle(
    "Code", parent=styles["Code"], fontSize=9, leading=14,
    backColor=LIGHT, borderColor=BORDER, borderWidth=0.8,
    borderPadding=8, spaceAfter=10,
)
style_bullet = ParagraphStyle(
    "Bullet", parent=style_body, spaceAfter=2,
)
style_cell = ParagraphStyle(
    "Cell", parent=styles["Normal"], fontSize=9, leading=12,
    textColor=colors.HexColor("#2b313a"),
)
style_cell_head = ParagraphStyle(
    "CellHead", parent=style_cell, fontName="Helvetica-Bold",
    textColor=colors.white,
)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.drawString(20 * mm, 12 * mm, "SIH26153 — NetWatch · How to Run")
    canvas.restoreState()


story = []

# ── Cover ──────────────────────────────────────────────────────
story.append(Spacer(1, 60 * mm))
story.append(Paragraph("SIH26153", style_cover_sub))
story.append(Spacer(1, 4 * mm))
story.append(Paragraph("NetWatch — How to Run", style_cover_title))
story.append(Spacer(1, 8 * mm))
story.append(Paragraph(
    "AI-Based Network Attack Forecasting from Network Traffic Data<br/>"
    "Counterfactual Cyber World Model · SIH-26153 · Problem Owner: NTRO",
    style_cover_sub,
))
story.append(Spacer(1, 30 * mm))
story.append(HRFlowable(width="60%", thickness=1.2, color=ACCENT, hAlign="CENTER"))
story.append(Spacer(1, 10 * mm))
story.append(Paragraph(
    "A step-by-step guide to setting up the environment, running the dashboard, "
    "ingesting traffic data and using the forecasting pipeline.",
    style_cover_sub,
))
story.append(PageBreak())

# ── 1. Overview ────────────────────────────────────────────────
story.append(Paragraph("1. Overview", style_h1))
story.append(Paragraph(
    "NetWatch is an offline, AI-based Network Attack Forecasting system. It ingests "
    "network traffic (PCAP, PCAPNG, CSV flow records or JSONL events, optionally "
    "wrapped in a ZIP archive), builds per-window network states, and uses a trained "
    "LSTM World Model plus an ensemble of detection engines to forecast the next "
    "attack stages. A counterfactual simulator evaluates defensive actions and "
    "recommends the one that minimises future risk. Everything is served through a "
    "Flask dashboard and runs fully offline — no cloud or external inference.",
    style_body,
))

# ── 2. Prerequisites ───────────────────────────────────────────
story.append(Paragraph("2. Prerequisites", style_h1))
story.append(ListFlowable(
    [
        ListItem(Paragraph("Python 3.10 or newer", style_bullet), leftIndent=14),
        ListItem(Paragraph("pip (comes with Python)", style_bullet), leftIndent=14),
        ListItem(Paragraph("A GitHub account / Git CLI only if you clone the repo", style_bullet), leftIndent=14),
        ListItem(Paragraph("Internet access only at setup time (installing packages); runtime is offline", style_bullet), leftIndent=14),
    ],
    bulletType="bullet",
    start="•",
))
story.append(Spacer(1, 4 * mm))

# ── 3. Setup ───────────────────────────────────────────────────
story.append(Paragraph("3. Project Setup", style_h1))
story.append(Paragraph("3.1 Clone the repository", style_h2))
story.append(Paragraph(
    "Clone the repository (or copy the project folder onto your machine).",
    style_body,
))
story.append(Paragraph(
    "git clone https://github.com/sihcodesprit/external_hackathon.git\n"
    "cd external_hackathon",
    style_code,
))

story.append(Paragraph("3.2 Create a virtual environment", style_h2))
story.append(Paragraph("Windows (PowerShell / Command Prompt):", style_body))
story.append(Paragraph(
    "python -m venv venv\n"
    "venv\\Scripts\\activate",
    style_code,
))
story.append(Paragraph("macOS / Linux:", style_body))
story.append(Paragraph(
    "python3 -m venv venv\n"
    "source venv/bin/activate",
    style_code,
))

story.append(Paragraph("3.3 Install dependencies", style_h2))
story.append(Paragraph(
    "pip install -r requirements.txt",
    style_code,
))
story.append(Paragraph(
    "The requirements include Flask, NumPy, scikit-learn, PyTorch, PyYAML, SHAP and "
    "pytest. A CPU-only PyTorch build is sufficient.",
    style_body,
))

story.append(Paragraph("3.4 Optional environment file", style_h2))
story.append(Paragraph(
    "Copy the template and edit as needed (the .env file is gitignored):",
    style_body,
))
story.append(Paragraph(
    "copy .env.example .env    # Windows\n"
    "cp .env.example .env      # macOS / Linux",
    style_code,
))

# ── 4. Get pre-trained models ──────────────────────────────────
story.append(Paragraph("4. Obtain Pre-trained Models (recommended)", style_h1))
story.append(Paragraph(
    "The repository ships with placeholder JSON linear checkpoints (NaN weights). "
    "Training real LSTM weights is done in Colab — one time — and produces a model "
    "ZIP that you upload to the dashboard.",
    style_body,
))
story.append(Paragraph("4.1 Train in Google Colab", style_h2))
story.append(ListFlowable(
    [
        ListItem(Paragraph(
            "Open <b>NetWatch_Colab.ipynb</b> in the repository on Google Colab.",
            style_bullet), leftIndent=14),
        ListItem(Paragraph(
            "Run all cells. The notebook trains the LSTM World Model, the ensemble "
            "baselines, the feature scaler and supporting artifacts.",
            style_bullet), leftIndent=14),
        ListItem(Paragraph(
            "It downloads a ZIP named <b>netwatch_trained_models.zip</b>.",
            style_bullet), leftIndent=14),
    ],
    bulletType="bullet",
    start="•",
))
story.append(Paragraph("4.2 Upload the ZIP to the dashboard", style_h2))
story.append(Paragraph(
    "After the dashboard is running (Section 5), open the <b>Models</b> page "
    "(/models) and drop the <b>netwatch_trained_models.zip</b> file. The .pt / .pkl / "
    ".json / .npz artifacts inside are extracted into data/data/models and the "
    "pipeline reloads with real weights.",
    style_body,
))

# ── 5. Run the dashboard ───────────────────────────────────────
story.append(Paragraph("5. Run the Dashboard", style_h1))
story.append(Paragraph(
    "While the virtual environment is active, from the project root:",
    style_body,
))
story.append(Paragraph(
    "python run.py",
    style_code,
))
story.append(Paragraph(
    "The server starts on <b>http://localhost:5000</b> (open it in your browser). "
    "The pipeline loads lazily on the first request; dashboard pages train/load "
    "models as needed and remain fully offline.",
    style_body,
))

story.append(Paragraph("5.1 CLI options", style_h2))
tbl_data = [
    [
        Paragraph("Command", style_cell_head),
        Paragraph("What it does", style_cell_head),
    ],
    [
        Paragraph("python run.py", style_cell),
        Paragraph("Start the dashboard (default port 5000)", style_cell),
    ],
    [
        Paragraph("python run.py --port 8080", style_cell),
        Paragraph("Start the dashboard on a custom port", style_cell),
    ],
    [
        Paragraph("python run.py --no-pipeline", style_cell),
        Paragraph("Skip pre-running the pipeline; serve pages only", style_cell),
    ],
    [
        Paragraph("python run.py --pipeline-only", style_cell),
        Paragraph("Run the pipeline end-to-end and print a JSON report, then exit", style_cell),
    ],
]
tbl = Table(tbl_data, colWidths=[60 * mm, 110 * mm])
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

# ── 6. Upload traffic ──────────────────────────────────────────
story.append(Paragraph("6. Ingest Network Traffic", style_h1))
story.append(Paragraph(
    "From the <b>Upload</b> page you can supply your own capture data. Supported "
    "formats:",
    style_body,
))
tbl_data = [
    [
        Paragraph("Type", style_cell_head),
        Paragraph("Description", style_cell_head),
        Paragraph("Example", style_cell_head),
    ],
    [
        Paragraph("PCAP / PCAPNG", style_cell),
        Paragraph("Raw packet captures (requires optional scapy to enable)", style_cell),
        Paragraph("capture.pcapng", style_cell),
    ],
    [
        Paragraph("CSV", style_cell),
        Paragraph("Flow-record/feature tables", style_cell),
        Paragraph("flows.csv", style_cell),
    ],
    [
        Paragraph("JSONL", style_cell),
        Paragraph("JSON events, one record per line", style_cell),
        Paragraph("events.jsonl", style_cell),
    ],
    [
        Paragraph("ZIP", style_cell),
        Paragraph("Any archive wrapping one of the above; the traffic file is "
                  "auto-detected (pcapng > pcap > csv > jsonl). A ZIP with only "
                  "model artifacts is treated as a model bundle.", style_cell),
        Paragraph("capture_bundle.zip", style_cell),
    ],
]
tbl = Table(tbl_data, colWidths=[32 * mm, 92 * mm, 46 * mm])
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
story.append(Spacer(1, 4 * mm))
story.append(Paragraph(
    "After ingestion the dashboard rebuilds network states, runs the forecast + "
    "counterfactual simulation, and every page reflects the new session data.",
    style_body,
))

# ── 7. Dashboard pages ─────────────────────────────────────────
story.append(Paragraph("7. Dashboard Pages", style_h1))
tbl_data = [
    [
        Paragraph("Page", style_cell_head),
        Paragraph("Route", style_cell_head),
        Paragraph("Content", style_cell_head),
    ],
    [
        Paragraph("Dashboard", style_cell), Paragraph("/dashboard", style_cell),
        Paragraph("Current risk, stage, recommendation and forecast summary", style_cell),
    ],
    [
        Paragraph("Topology", style_cell), Paragraph("/topology", style_cell),
        Paragraph("Dynamic network topology of the ingested session", style_cell),
    ],
    [
        Paragraph("Forecast Radar", style_cell), Paragraph("/radar", style_cell),
        Paragraph("Future risk timeline", style_cell),
    ],
    [
        Paragraph("Attack Graph", style_cell), Paragraph("/graph", style_cell),
        Paragraph("Predictive attack graph (current + predicted stages)", style_cell),
    ],
    [
        Paragraph("Counterfactual", style_cell), Paragraph("/counterfactual", style_cell),
        Paragraph("What-if defence simulation and recommended action", style_cell),
    ],
    [
        Paragraph("MITRE Stages", style_cell), Paragraph("/stages", style_cell),
        Paragraph("Attack stage timeline + MITRE trajectory", style_cell),
    ],
    [
        Paragraph("Explainability", style_cell), Paragraph("/explainability", style_cell),
        Paragraph("SHAP / top contributing features", style_cell),
    ],
    [
        Paragraph("Ensemble", style_cell), Paragraph("/ensemble", style_cell),
        Paragraph("Multi-engine detection consensus scores", style_cell),
    ],
    [
        Paragraph("Models", style_cell), Paragraph("/models", style_cell),
        Paragraph("Install model ZIPs, view active artifacts, reload", style_cell),
    ],
    [
        Paragraph("Evaluation", style_cell), Paragraph("/evaluation", style_cell),
        Paragraph("World Model vs baseline metrics", style_cell),
    ],
    [
        Paragraph("Test Center", style_cell), Paragraph("/test-center", style_cell),
        Paragraph("Model validation checks", style_cell),
    ],
    [
        Paragraph("Scenarios", style_cell), Paragraph("/scenarios", style_cell),
        Paragraph("Ad-hoc scenario / data explorer", style_cell),
    ],
    [
        Paragraph("Upload", style_cell), Paragraph("/upload", style_cell),
        Paragraph("Ingest PCAP / CSV / JSONL / ZIP traffic or model bundles", style_cell),
    ],
]
tbl = Table(tbl_data, colWidths=[40 * mm, 40 * mm, 90 * mm])
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

# ── 8. Tests ───────────────────────────────────────────────────
story.append(Paragraph("8. Run Tests", style_h1))
story.append(Paragraph(
    "From the project root, with the virtual environment active:",
    style_body,
))
story.append(Paragraph(
    "python -m pytest tests/ -q",
    style_code,
))
story.append(Paragraph(
    "Expected baseline: <b>62 passed, 7 failed</b>. The 7 failures are pre-existing "
    "legacy tests ('List' import in pipeline.py, synthetic load_data generator "
    "removed, missing-world-model path) and are unrelated to the current workflow.",
    style_body,
))

# ── 9. Troubleshooting ─────────────────────────────────────────
story.append(Paragraph("9. Troubleshooting", style_h1))
tbl_data = [
    [
        Paragraph("Symptom", style_cell_head),
        Paragraph("Solution", style_cell_head),
    ],
    [
        Paragraph("'Python' is not recognized", style_cell),
        Paragraph("Ensure Python 3.10+ is installed and on PATH; or use 'py -3' on Windows.", style_cell),
    ],
    [
        Paragraph("Port 5000 already in use", style_cell),
        Paragraph("Run 'python run.py --port 8080' and open http://localhost:8080.", style_cell),
    ],
    [
        Paragraph("ModuleNotFoundError when running run.py", style_cell),
        Paragraph("Set PYTHONPATH to the project root, e.g. $env:PYTHONPATH = '<project>'; then run it.", style_cell),
    ],
    [
        Paragraph("Forecast shows placeholder / zero risk", style_cell),
        Paragraph("Train and upload netwatch_trained_models.zip via the Models page (Section 4).", style_cell),
    ],
    [
        Paragraph("Uploaded ZIP not detected", style_cell),
        Paragraph("ZIP must contain a .pcapng/.pcap/.csv/.jsonl member to be treated as traffic.", style_cell),
    ],
    [
        Paragraph("Text truncation / encoding issues on Windows", style_cell),
        Paragraph("Apply 'git config core.autocrlf true' and re-clone, or run with UTF-8 console.", style_cell),
    ],
]
tbl = Table(tbl_data, colWidths=[62 * mm, 108 * mm])
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
story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER))
story.append(Spacer(1, 3 * mm))
story.append(Paragraph(
    "NetWatch · SIH26153 · Counterfactual Cyber World Model — Problem Owner: NTRO. "
    "Generated from make_howto_pdf.py.",
    ParagraphStyle("foot", parent=style_body, textColor=GREY, fontSize=8.5, alignment=TA_LEFT),
))

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=20 * mm, rightMargin=20 * mm,
    topMargin=20 * mm, bottomMargin=18 * mm,
    title="SIH26153 — NetWatch: How to Run",
    author="SIH26153 Team",
)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("Wrote", OUT)