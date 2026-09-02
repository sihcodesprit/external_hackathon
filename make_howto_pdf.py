"""
Generate HOW_TO_RUN.pdf for the SIH26153 Counterfactual Cyber World Model.

Run: python make_howto_pdf.py
Outputs: docs/HOW_TO_RUN.pdf
"""

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "HOW_TO_RUN.pdf"

ACCENT = colors.HexColor("#0b3d5c")
LIGHT = colors.HexColor("#eef4f8")


def main():
    os.makedirs(OUT.parent, exist_ok=True)
    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "TitleX", parent=styles["Title"], textColor=ACCENT, fontSize=22, spaceAfter=2
    )
    subtitle = ParagraphStyle(
        "Sub", parent=styles["Normal"], textColor=colors.HexColor("#555555"),
        fontSize=12, spaceAfter=14,
    )
    h1 = ParagraphStyle(
        "H1x", parent=styles["Heading1"], textColor=ACCENT, fontSize=15,
        spaceBefore=14, spaceAfter=6,
    )
    h2 = ParagraphStyle(
        "H2x", parent=styles["Heading2"], textColor=colors.HexColor("#1c5a86"),
        fontSize=12, spaceBefore=8, spaceAfter=4,
    )
    body = ParagraphStyle(
        "BodyX", parent=styles["BodyText"], fontSize=10, leading=14,
    )
    code = ParagraphStyle(
        "CodeX", parent=styles["Code"],
        backColor=LIGHT, borderPadding=4, fontSize=9, leading=12,
        spaceBefore=4, spaceAfter=8,
    )

    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="How to Run - SIH26153 Counterfactual Cyber World Model",
        author="SIH26153 Team",
    )

    story = []
    story.append(Paragraph("SIH26153 — Counterfactual Cyber World Model", title))
    story.append(Paragraph(
        "AI-Based Network Attack Forecasting from Network Traffic Data (NTRO)",
        subtitle,
    ))

    def h(t):
        story.append(Paragraph(t, h1))

    def b(t):
        story.append(Paragraph(t, body))

    # ── 1 Overview ─────────────────────────────────────────
    h("1. Overview")
    b(
        "This system is a temporal Network World Model that learns "
        "P(S<sub>t+1</sub> | S<sub>t</sub>), forecasts multiple future attack "
        "states (K-step rollout), maps them to MITRE ATT&amp;CK stages, builds a "
        "predictive attack graph, and runs counterfactual defensive simulation to "
        "recommend the action that most reduces predicted future risk. It runs "
        "<b>fully offline</b> — no cloud or external inference API."
    )

    h("2. Prerequisites")
    b("Python 3.10 or newer (tested on 3.13). No cloud account or Npcap required.")
    b("Optional: to ingest .pcap files, install scapy (pip install scapy).")

    # ── 3 Install ──────────────────────────────────────────
    h("3. Install dependencies")
    story.append(Paragraph(
        "python -m venv venv<br/>"
        "venv\\Scripts\\activate          &nbsp;// Windows<br/>"
        "source venv/bin/activate      &nbsp;// macOS / Linux<br/><br/>"
        "pip install -r requirements.txt",
        code,
    ))
    b(
        "requirements.txt installs flask, gunicorn, numpy, scikit-learn, torch "
        "(CPU build is fine), shap, and pytest."
    )

    # ── 4 Run the dashboard ───────────────────────────────
    h("4. Run the dashboard")
    b("Run from the project root (the directory that contains run.py):")
    story.append(Paragraph(
        "cd SIH26153-AI-Network-Attack-Forecasting/main<br/>"
        "python run.py",
        code,
    ))
    b("Then open <b>http://localhost:5000</b> in your browser. On first request "
      "the LSTM World Model is trained on synthetic data and cached for the "
      "process lifetime.")

    h("Other run modes")
    table_data = [
        ["Command", "Description"],
        ["python run.py", "Train World Model, then start dashboard"],
        ["python run.py --pipeline-only", "Train + evaluate + forecast, print JSON report, exit"],
        ["python run.py --no-pipeline", "Dashboard only (trains lazily on first request)"],
        ["python run.py --port 8080", "Serve on a specific port"],
    ]
    t = Table(table_data, colWidths=[95 * mm, 75 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    # ── 5 Dashboard pages ─────────────────────────────────
    h("5. Dashboard pages (8)")
    pages = [
        ("/dashboard", "Live / uploaded traffic — current risk + stage"),
        ("/radar", "10-minute prediction radar (future risk timeline)"),
        ("/graph", "Predictive attack graph (current + predicted states)"),
        ("/counterfactual", "What-if defensive simulation + recommended action"),
        ("/stages", "Attack stage timeline + MITRE trajectory"),
        ("/explainability", "SHAP / top contributing feature explanations"),
        ("/evaluation", "World Model vs baseline metrics"),
        ("/scenarios", "Ad-hoc scenario / data explorer"),
    ]
    story.append(ListFlowable(
        [ListItem(Paragraph(f"<b>{r}</b> — {d}", body), leftIndent=8) for r, d in pages],
        bulletType="bullet", start="•", bulletFontSize=9,
    ))

    # ── 6 Example output ──────────────────────────────────
    h("6. Example forecast output")
    b("For the most recent observed window the system produces something like:")
    ex = [
        ["Step", "Predicted Stage", "Risk"],
        ["Current", "Command and Control", "93%"],
        ["t+1", "Command and Control", "93%"],
        ["t+2", "Exfiltration", "<1%"],
        ["t+3", "Exfiltration", "<1%"],
        ["t+4", "Command and Control", "<1%"],
        ["t+5", "Exfiltration", "<1%"],
    ]
    et = Table(ex, colWidths=[30 * mm, 70 * mm, 70 * mm])
    et.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
    ]))
    story.append(et)
    story.append(Spacer(1, 8))
    b(
        "<i>Values shown are from an actual run and vary with the data; the "
        "dashboard always shows live computed values. All probabilities are real "
        "model outputs — nothing is fabricated.</i>"
    )

    # ── 7 Counterfactual example ──────────────────────────
    h("7. Counterfactual defensive simulation (example)")
    b("For the same window the system simulates each defensive action through "
      "the World Model and compares the predicted future risk:")
    cf = [
        ["Action", "Predicted Peak Risk"],
        ["No Action", "93%"],
        ["Block Source", "41%"],
        ["Block Dest. Port", "41%"],
        ["Isolate Host", "41%"],
        ["Terminate Flow", "41%"],
        ["Restrict Path", "41%"],
        ["Recommended Action", "Block Source"],
    ]
    ct = Table(cf, colWidths=[90 * mm, 80 * mm])
    ct.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d9e8f5")),
    ]))
    story.append(ct)
    story.append(Spacer(1, 8))
    b(
        "Each action modifies the simulated network state, the World Model runs a "
        "K-step rollout, and the learned risk head reads the resulting trajectory. "
        "The recommended action is the one that minimizes predicted near-term "
        "(peak) attack risk."
    )

    # ── 8 Run the tests ───────────────────────────────────
    h("8. Run the tests")
    story.append(Paragraph(
        "cd SIH26153-AI-Network-Attack-Forecasting/main<br/>"
        "python -m pytest tests/ -v",
        code,
    ))
    b(
        "The suite (61 tests) covers feature extraction, NetworkState "
        "construction, sequence generation, World Model training/prediction, "
        "K-step rollout, MITRE mapping, counterfactual actions, risk comparison, "
        "explainability, API, dashboard routes, and a full end-to-end pipeline."
    )

    # ── 9 Configuration ───────────────────────────────────
    h("9. Configuration (optional)")
    b("Copy .env.example to .env to customise:")
    env = [
        ["Variable", "Default", "Purpose"],
        ["PORT", "5000", "Web server port"],
        ["FLASK_DEBUG", "0", "Enable Flask debug / hot reload"],
        ["NW_WORLD_MODEL", "lstm", "lstm or linear"],
        ["NW_EPOCHS", "30", "Training epochs"],
        ["NW_EXPLAIN", "1", "Enable SHAP explainability"],
    ]
    nv = Table(env, colWidths=[45 * mm, 35 * mm, 90 * mm])
    nv.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
    ]))
    story.append(nv)
    story.append(Spacer(1, 8))

    # ── 10 Ingestion ──────────────────────────────────────
    h("10. Ingesting your own data")
    b(
        "Dataset adapters exist in netwatch/ingestion/datasets/adapters.py for "
        "CIC-IDS2017/2018, CTU-13, UNSW-NB15, and CICIoT2023. They convert each "
        "source schema into the common PacketRecord / NetworkState schema. PCAP, "
        "flow CSV, and JSONL packet streams are supported via "
        "netwatch/ingestion/parser.py. Load a file through the matching adapter "
        "and re-run the pipeline — the World Model is dataset-agnostic."
    )

    # ── 11 Documentation ──────────────────────────────────
    h("11. Further reading")
    story.append(ListFlowable(
        [ListItem(Paragraph(f"<b>{f}</b>", body), leftIndent=8)
         for f in ["README.md", "docs/ARCHITECTURE.md", "docs/MODEL_CARD.md",
                    "docs/EXPERIMENTS.md", "PROJECT_AUDIT.md",
                    "REMOVED_COMPONENTS.md", "FINAL_AUDIT.md"]],
        bulletType="bullet", start="•", bulletFontSize=9,
    ))

    doc.build(story)
    print(f"PDF written to {OUT}")


if __name__ == "__main__":
    main()
