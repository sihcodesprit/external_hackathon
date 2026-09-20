import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { ThreatHeader } from "../components/analysis/ThreatHeader";
import { TrafficSummary } from "../components/analysis/TrafficSummary";
import { Card, Grid } from "../components/ui/primitives";
import { MetricCard } from "../components/ui/displays";
import { ForecastTimeline } from "../components/charts/ForecastTimeline";
import { RadarChart, DetectorList } from "../components/charts/RadarChart";
import { fmtInt } from "../utils/format";
import { Button } from "../components/ui/Button";

export default function Overview({ bare = false }: { bare?: boolean } = {}) {
  const { doc, clear } = useAnalysis();

  return (
    <div>
      {!bare && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, letterSpacing: 0.2 }}>Live Threat Overview</h1>
            <p style={{ fontSize: 12.5, color: palette.textMuted, marginTop: 4 }}>
              Real forecasts derived from the LSTM world model, ensemble threat scoring and MITRE mapping.
            </p>
          </div>
          {doc && (
            <Button variant="ghost" size="sm" onClick={clear}>
              Clear analysis
            </Button>
          )}
        </div>
      )}

      <RequireAnalysis>
        {(doc) => (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <ThreatHeader doc={doc} />

            <Grid cols="repeat(4, 1fr)" gap={12}>
              <MetricCard label="Records" value={fmtInt(doc.traffic_summary?.n_packets)} sub={`${fmtInt(doc.traffic_summary?.n_flows)} flows`} />
              <MetricCard label="Network states" value={fmtInt(doc.n_states)} sub="windowed feature vectors" tone="accent" />
              <MetricCard label="Hosts" value={fmtInt(doc.traffic_summary?.n_hosts)} sub={doc.traffic_summary?.n_hosts ? "discovered via entity resolution" : undefined} />
              <MetricCard label="Duration" value={`${(doc.traffic_summary?.duration_seconds ?? 0).toFixed(1)}s`} sub="capture time span" />
            </Grid>

            <Grid cols="2fr 1fr" gap={14}>
              <Card title="Forecast trajectory" subtitle="World model K-step projection of network risk and stage">
                {doc.forecast ? <ForecastTimeline forecast={doc.forecast} /> : null}
              </Card>
              <Card title="Ensemble detectors" subtitle="Multi-engine threat consensus">
                {doc.ensemble ? <DetectorList detectors={doc.ensemble.detectors} /> : null}
              </Card>
            </Grid>

            <Grid cols="2fr 1fr" gap={14}>
              <TrafficSummary summary={doc.traffic_summary} />
              <Card title="Detector radar" subtitle="Normalized scores across engines">
                {doc.ensemble?.radar_data ? <RadarChart radar={doc.ensemble.radar_data} /> : null}
              </Card>
            </Grid>
          </div>
        )}
      </RequireAnalysis>
    </div>
  );
}