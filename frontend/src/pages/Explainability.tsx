import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card, Grid, Tag } from "../components/ui/primitives";
import { FeatureBars } from "../components/charts/FeatureBars";

interface Contrib {
  feature: string;
  contribution: number;
  sign?: string;
}

export default function Explainability({ bare = false }: { bare?: boolean } = {}) {
  const { doc } = useAnalysis();
  const cur = doc?.forecast?.current;
  const expl = cur?.explanation as
    | { explanation_type?: string; contributions?: Contrib[]; summary?: string; top_features?: Contrib[] }
    | undefined;
  const temporal = doc?.forecast?.temporal_explanation as
    | {
        status?: string;
        temporal_contributions?: Array<{ step: number; risk: number; stage: string; top_features: Contrib[] }>;
        escalation_drivers?: string[];
        stabilization_drivers?: string[];
        summary?: string;
      }
    | undefined;

  const bars: Array<{ feature: string; contribution: number }> = (expl?.contributions ?? []).map((c) => ({
    feature: c.feature,
    contribution: parseFloat((c.sign === "-" ? -1 : 1) * c.contribution),
  }));

  return (
    <div>
      {!bare && (
        <>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Explainability</h1>
          <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
            SHAP-based attribution of the current forecast and temporal evolution of the driving features.
          </p>
        </>
      )}

      <RequireAnalysis>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card
            title="Current state — feature attribution"
            subtitle={expl ? `engine: ${expl.explanation_type ?? "unknown"}` : undefined}
          >
            {expl?.summary && (
              <div style={{ fontSize: 13, color: palette.textDim, marginBottom: 14, lineHeight: 1.6 }}>
                {expl.summary}
              </div>
            )}
            {bars.length ? (
              <FeatureBars features={bars} />
            ) : (
              <div style={{ fontSize: 12.5, color: palette.textMuted }}>No attribution data available.</div>
            )}
          </Card>

          {temporal && temporal.status !== "no_steps" && temporal.temporal_contributions?.length ? (
            <Grid cols="2fr 1fr" gap={14}>
              <Card title="Temporal driver evolution" subtitle="Top contributing features per forecast step">
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {temporal.temporal_contributions.map((t) => (
                    <div key={t.step}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <span className="mono" style={{ fontSize: 12, color: palette.accent }}>
                          t+{t.step} · {t.stage}
                        </span>
                        <span className="mono" style={{ fontSize: 12, color: palette.textDim }}>
                          risk {((t.risk ?? 0) * 100).toFixed(1)}
                        </span>
                      </div>
                      <FeatureBars
                        features={t.top_features.map((f) => ({ feature: f.feature, contribution: f.contribution }))}
                        color="#38bdf8"
                      />
                    </div>
                  ))}
                </div>
              </Card>
              <Card title="Driver summary" subtitle="Model narrative">
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 650, color: palette.danger, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 6 }}>
                      Escalation drivers
                    </div>
                    {(temporal.escalation_drivers ?? []).map((f) => (
                      <div key={f} style={{ marginBottom: 4 }}>
                        <Tag color="#f87171">{f.replace(/_/g, " ")}</Tag>
                      </div>
                    ))}
                    {(temporal.escalation_drivers ?? []).length === 0 && (
                      <div style={{ fontSize: 11.5, color: palette.textMuted }}>None identified</div>
                    )}
                  </div>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 650, color: palette.good, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 6 }}>
                      Stabilizing drivers
                    </div>
                    {(temporal.stabilization_drivers ?? []).map((f) => (
                      <div key={f} style={{ marginBottom: 4 }}>
                        <Tag color="#34d399">{f.replace(/_/g, " ")}</Tag>
                      </div>
                    ))}
                    {(temporal.stabilization_drivers ?? []).length === 0 && (
                      <div style={{ fontSize: 11.5, color: palette.textMuted }}>None identified</div>
                    )}
                  </div>
                  {temporal.summary && (
                    <div style={{ fontSize: 12, color: palette.textDim, lineHeight: 1.6, paddingTop: 4 }}>
                      {temporal.summary}
                    </div>
                  )}
                </div>
              </Card>
            </Grid>
          ) : (
            <div style={{ fontSize: 12.5, color: palette.textMuted }}>
              Temporal explanation requires a multi-step forecast.
            </div>
          )}
        </div>
      </RequireAnalysis>
    </div>
  );
}