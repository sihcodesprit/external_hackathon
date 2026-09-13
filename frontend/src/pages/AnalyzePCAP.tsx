import { useAnalysis } from "../store/analysisContext";
import { palette } from "../styles/theme";
import { FileUploader } from "../components/analysis/FileUploader";
import { JobProgress } from "../components/analysis/JobProgress";
import { TrafficSummary } from "../components/analysis/TrafficSummary";
import { Card } from "../components/ui/primitives";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";

export default function AnalyzePCAP() {
  const { doc, job, running, status, error } = useAnalysis();
  const navigate = useNavigate();

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Analyze PCAP</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Upload a raw capture and the engine ingests it, builds network states, forecasts the assault
        trajectory and runs the threat ensemble — with live progress.
      </p>

      <FileUploader />

      {(running || status === "error") && doc === null && (
        <div style={{ marginTop: 16 }}>
          <JobProgress job={job} />
          {status === "error" && error && (
            <div
              style={{
                marginTop: 10,
                padding: "10px 14px",
                borderRadius: 8,
                background: "rgba(239,68,68,0.12)",
                border: "1px solid rgba(239,68,68,0.4)",
                color: "#f87171",
                fontSize: 12,
                lineHeight: 1.55,
              }}
            >
              {error}
            </div>
          )}
        </div>
      )}

      {doc && (
        <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 16 }}>
          <Card title="Analysis complete" subtitle={`${doc.filename}${doc.member ? ` · ${doc.member}` : ""}`}>
            <TrafficSummary summary={doc.traffic_summary} />
            <div style={{ marginTop: 16, display: "flex", gap: 10 }}>
              <Button onClick={() => navigate("/")}>View overview</Button>
              <Button variant="outline" onClick={() => navigate("/forecast")}>Open forecast</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}