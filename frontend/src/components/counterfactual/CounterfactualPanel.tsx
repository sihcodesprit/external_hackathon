import { palette } from "../../styles/theme";
import type { AnalysisDoc } from "../../types";
import { Card } from "../ui/primitives";
import { stageColor } from "../../styles/theme";
import { CounterfactualResult } from "../../types";

export function CounterfactualPanel({ doc, compact }: { doc: AnalysisDoc; compact?: boolean }) {
  const cf = doc.counterfactual;
  if (!cf) return null;
  const results = Object.values(cf.results ?? {});
  const rec = cf.recommendation;

  return (
    <Card title={compact ? "Defense simulation" : "Counterfactual defense simulation"} subtitle="Predicted risk under each defensive action">
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div
          style={{
            padding: "12px 14px",
            borderRadius: 8,
            border: `1px solid ${palette.accentBorder}`,
            background: palette.accentSoft,
            display: "flex",
            flexWrap: "wrap",
            gap: 14,
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ fontSize: 13, color: palette.text }}>
            Recommended action:{" "}
            <span style={{ color: palette.accent, fontWeight: 700 }}>{rec?.recommended_label ?? "No Action"}</span>
          </div>
          <div className="mono" style={{ fontSize: 12, color: palette.textDim }}>
            peak risk {(rec?.baseline_risk ?? 0).toFixed(2)} → {(rec?.counterfactual_risk ?? 0).toFixed(2)}
            {typeof rec?.risk_reduction_pct_points === "number" && rec.risk_reduction_pct_points !== 0 && (
              <span style={{ color: palette.good }}> · -{Math.abs(rec.risk_reduction_pct_points).toFixed(1)} pts</span>
            )}
          </div>
        </div>
        {!compact && rec?.reason && (
          <div style={{ fontSize: 12.5, color: palette.textDim, lineHeight: 1.6 }}>{rec.reason}</div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {results.map((r) => (
            <ActionRow key={r.action_id} action={r} recommended={r.action_id === rec?.recommended_action} />
          ))}
        </div>
      </div>
    </Card>
  );
}

function ActionRow({ action, recommended }: { action: CounterfactualResult["results"][string]; recommended: boolean }) {
  const color = recommended ? palette.accent : palette.textDim;
  const maxPts = Math.max(...action.risk_trajectory);
  return (
    <div
      style={{
        padding: "10px 12px",
        borderRadius: 8,
        border: `1px solid ${recommended ? palette.accentBorder : palette.borderSoft}`,
        background: recommended ? palette.accentSoft : "transparent",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: recommended ? palette.accent : palette.text }}>
          {action.label}
        </span>
        <span className="mono" style={{ fontSize: 11.5, color: palette.textDim }}>
          peak {action.peak_risk.toFixed(2)} · final {action.final_risk.toFixed(2)}
        </span>
      </div>
      <div style={{ marginTop: 8, display: "flex", alignItems: "flex-end", gap: 2, height: 26 }}>
        {action.risk_trajectory.map((v, i) => {
          const h = Math.max(3, (v / Math.max(1e-6, maxPts)) * 24);
          const c = recommended ? stageColor("Benign") : palette.border;
          return <div key={i} style={{ flex: 1, height: h, background: c, borderRadius: "2px 2px 0 0", opacity: recommended ? 0.85 : 0.7 }} />;
        })}
      </div>
    </div>
  );
}