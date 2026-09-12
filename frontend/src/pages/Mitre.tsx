import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card } from "../components/ui/primitives";
import { stageColor } from "../styles/theme";

export default function Mitre() {
  const { doc } = useAnalysis();
  const traj = doc?.mitre_trajectory ?? [];

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>MITRE Trajectory</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        The predicted attack progression mapped to MITRE ATT&CK tactics and techniques. Mapping is
        deterministic and only claims a technique when the stage evidence supports it.
      </p>

      <RequireAnalysis>
        {traj.length === 0 ? (
          <Card title="MITRE mapping">
            <div style={{ fontSize: 12.5, color: palette.textMuted }}>No attack stages to map — traffic appears benign or no forecast is available.</div>
          </Card>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {traj.map((t, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 16,
                  alignItems: "center",
                  padding: "12px 16px",
                  borderRadius: 10,
                  border: `1px solid ${t.has_mitre ? palette.accentBorder : palette.borderSoft}`,
                  background: t.has_mitre ? palette.accentSoft : "rgba(16,24,42,0.28)",
                  opacity: t.has_mitre ? 1 : 0.55,
                }}
              >
                <span className="mono" style={{ fontSize: 12, color: palette.textMuted, width: 40 }}>t{i === 0 ? "" : `+${i}`}</span>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: t.has_mitre ? stageColor(t.stage) : palette.border,
                    boxShadow: t.has_mitre ? `0 0 10px ${stageColor(t.stage)}70` : "none",
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: palette.text }}>{t.stage}</div>
                  <div style={{ fontSize: 11, color: palette.textDim }}>
                    tactic: <span className="mono">{t.tactic}</span>
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="mono" style={{ fontSize: 13, color: t.has_mitre ? palette.accent : palette.textMuted }}>
                    {t.has_mitre ? t.technique_id : "UNKNOWN"}
                  </div>
                  <div style={{ fontSize: 11, color: palette.textMuted }}>{t.technique_name}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </RequireAnalysis>
    </div>
  );
}