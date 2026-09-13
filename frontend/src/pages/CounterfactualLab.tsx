import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card } from "../components/ui/primitives";
import { CounterfactualPanel } from "../components/counterfactual/CounterfactualPanel";

export default function CounterfactualLab() {
  const { doc } = useAnalysis();
  const cf = doc?.counterfactual;

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Counterfactual Defense Lab</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        The world model simulates what happens to near-term risk if the SOC applies each defensive
        action, then recommends the option with the largest predicted risk reduction.
      </p>

      <RequireAnalysis>
        {(d) => (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <CounterfactualPanel doc={d} />

          {cf?.recommendation && (
              <Card title="Recommendation rationale" subtitle="Simulated peak-risk comparison">
                <div style={{ fontSize: 13, color: palette.textDim, lineHeight: 1.7 }}>
                  {cf.recommendation.reason}
                </div>
                <div
                  style={{
                    marginTop: 12,
                    padding: "12px 14px",
                    borderRadius: 8,
                    background: "rgba(16,24,42,0.3)",
                    border: `1px solid ${palette.borderSoft}`,
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 24,
                  }}
                >
                  <Stat label="Simulation horizon" value={`${cf.k} steps`} />
                  <Stat label="Effect window" value={`${cf.effect_window} states`} />
                  <Stat label="Baseline peak risk" value={cf.recommendation.baseline_risk.toFixed(3)} />
                  <Stat label="Counterfactual risk" value={cf.recommendation.counterfactual_risk.toFixed(3)} tone="accent" />
                  <Stat label="Risk reduction" value={`-${Math.abs(cf.recommendation.risk_reduction_pct_points).toFixed(1)} pts`} tone="good" />
                </div>
              </Card>
            )}
          </div>
        )}
      </RequireAnalysis>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "accent" | "good" }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 15, fontWeight: 650, color: tone === "accent" ? palette.accent : tone === "good" ? palette.good : palette.text }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: palette.textMuted, letterSpacing: 0.5, textTransform: "uppercase", marginTop: 2 }}>
        {label}
      </div>
    </div>
  );
}