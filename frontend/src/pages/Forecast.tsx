import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card, Grid, KeyValue } from "../components/ui/primitives";
import { MetricCard } from "../components/ui/displays";
import { ForecastTimeline } from "../components/charts/ForecastTimeline";
import { stageColor } from "../styles/theme";
import { fmtNum } from "../utils/format";

export default function Forecast({ bare = false }: { bare?: boolean } = {}) {
  const { doc } = useAnalysis();
  const fc = doc?.forecast;
  const cur = fc?.current;
  const future = fc?.future ?? [];

  return (
    <div>
      {!bare && (
        <>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Forecast & Projection</h1>
          <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
            The LSTM world model projects network risk and attack stage forward over the horizon.
          </p>
        </>
      )}

      <RequireAnalysis>
        {fc ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Grid cols="repeat(4, 1fr)" gap={12}>
              <MetricCard
                label="Current risk"
                value={((cur?.risk ?? 0) * 100).toFixed(1)}
                tone="danger"
                sub={cur?.stage ?? "Benign"}
              />
              <MetricCard label="Forecast horizon" value={`${fc.k ?? future.length} steps`} sub="K-step projection" tone="accent" />
              <MetricCard
                label="Peak projected risk"
                value={future.length > 0 ? (Math.max(...future.map((s) => (s.risk ?? 0) * 100))).toFixed(1) : "—"}
                sub={future[future.length - 1]?.stage ?? "—"}
              />
              <MetricCard label="Confidence" value={cur?.confidence != null ? `${(cur.confidence * 100).toFixed(0)}%` : "—"} />
            </Grid>

            <Card title="Risk projection" subtitle={`from "${cur?.stage ?? "Benign"}"`}>
              <ForecastTimeline forecast={fc} />
            </Card>

            {future.length > 0 && (
              <Card title="Step-by-step projection" subtitle="Stage, risk and confidence per forecast step">
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {future.map((s) => (
                    <div
                      key={s.step}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 16,
                        padding: "10px 14px",
                        borderRadius: 9,
                        border: `1px solid ${palette.borderSoft}`,
                        background: "rgba(16,24,42,0.28)",
                      }}
                    >
                      <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: palette.accent, width: 34 }}>
                        t+{s.step}
                      </span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, color: palette.text }}>{s.stage}</div>
                        <div style={{ height: 5, background: palette.border, borderRadius: 99, marginTop: 6, overflow: "hidden" }}>
<div
                        style={{
                          width: `${Math.min(100, (s.risk ?? 0) * 100).toFixed(0)}%`,
                          height: "100%",
                          background: stageColor(s.stage),
                        }}
                      />
                        </div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: stageColor(s.stage) }}>
                          {((s.risk ?? 0) * 100).toFixed(1)}
                        </div>
                        <div className="mono" style={{ fontSize: 10, color: palette.textMuted }}>
                          {s.confidence != null ? `conf ${(s.confidence * 100).toFixed(0)}%` : ""}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {cur?.explanation && (
              <Card title="Current state explanation" subtitle="Why the model believes this stage">
                <div style={{ fontSize: 12.5, color: palette.textDim, lineHeight: 1.6, marginBottom: 10 }}>
                  {cur.explanation.summary ?? "No explanation generated for the current state."}
                </div>
                {Array.isArray(cur.explanation.top_features) && cur.explanation.top_features.length > 0 && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                    {cur.explanation.top_features.map((f) => (
                      <KeyValue key={f.feature} k={f.feature} v={fmtNum(f.contribution, 2)} mono />
                    ))}
                  </div>
                )}
              </Card>
            )}
          </div>
        ) : (
          <div style={{ fontSize: 12.5, color: palette.textMuted }}>The forecast is produced after a capture is loaded.</div>
        )}
      </RequireAnalysis>
    </div>
  );
}
