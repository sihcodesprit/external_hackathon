import { useAnalysis } from "../store/analysisContext";
import { palette } from "../styles/theme";
import { FileUploader } from "../components/analysis/FileUploader";
import { JobProgress } from "../components/analysis/JobProgress";
import { TrafficSummary } from "../components/analysis/TrafficSummary";
import { Card } from "../components/ui/primitives";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";

export default function AnalyzePCAP() {
  const { doc, job, running } = useAnalysis();
  const navigate = useNavigate();

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Analyze PCAP</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Upload a raw capture and the engine ingests it, builds network states, forecasts the assault
        trajectory and runs the threat ensemble — with live progress.
      </p>

      <FileUploader />

      {running && doc === null && (
        <div style={{ marginTop: 16 }}>
          <JobProgress job={job} />
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