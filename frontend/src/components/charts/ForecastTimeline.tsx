import { palette } from "../../styles/theme";
import type { ForecastBlock } from "../../types";
import { threatGaugeColor } from "../../styles/theme";

export function ForecastTimeline({ forecast }: { forecast: ForecastBlock }) {
  const currentRisk = (forecast.current ?? 0) as number | undefined;
  const future = forecast.future ?? [];
  const steps = [
    { step: 0, stage: "Current", risk: (currentRisk ?? 0) * 100, current: true },
    ...future.map((f) => ({ step: f.step, stage: f.stage, risk: (f.risk ?? 0) * 100, current: false })),
  ];
  const maxRisk = Math.max(1, ...steps.map((s) => s.risk));

  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${Math.max(1, steps.length)}, minmax(0, 1fr))`,
          gap: 8,
          alignItems: "end",
          height: 150,
        }}
      >
        {steps.map((s) => {
          const color = threatGaugeColor(riskLevel(s.risk));
          const h = (s.risk / maxRisk) * 120;
          return (
            <div key={s.step} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, height: "100%", justifyContent: "flex-end" }}>
              <span className="mono" style={{ fontSize: 10.5, color: palette.textDim }}>
                {(s.risk ?? 0).toFixed(1)}
              </span>
              <div
                style={{
                  width: "100%",
                  maxWidth: 42,
                  height: Math.max(3, h),
                  borderRadius: "6px 6px 2px 2px",
                  background: `linear-gradient(180deg, ${color}, ${color}55)`,
                  border: `1px solid ${color}40`,
                  transition: "height 500ms ease",
                }}
              />
              <div style={{ fontSize: 9.5, color: s.current ? palette.accent : palette.textDim, textAlign: "center", lineHeight: 1.2 }}>
                {s.stage}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 10 }}>
        <div style={{ fontSize: 11, color: palette.textDim, fontWeight: 600, marginBottom: 8 }}>Risk trajectory</div>
        <svg viewBox="0 0 460 70" width="100%" height={70}>
          {steps.map((s, i) => {
            const x = (i / Math.max(1, steps.length - 1)) * 440;
            const y = 56 - (s.risk / 100) * 44;
            return (
              <g key={s.step}>
                {i > 0 && (
                  <line
                    x1={(i - 1) / Math.max(1, steps.length - 1) * 440}
                    y1={56 - (steps[i - 1].risk / 100) * 44}
                    x2={x}
                    y2={y}
                    stroke={threatGaugeColor(riskLevel(s.risk))}
                    strokeWidth={1.6}
                    opacity={0.6}
                  />
                )}
                <circle cx={x} cy={y} r={3.4} fill={threatGaugeColor(riskLevel(s.risk))} />
              </g>
            );
          })}
          <line x1={0} y1={56} x2={440} y2={56} stroke={palette.border} strokeWidth={1} />
        </svg>
      </div>
    </div>
  );
}

function riskLevel(v: number): string {
  if (v >= 75) return "CRITICAL";
  if (v >= 55) return "HIGH";
  if (v >= 30) return "MEDIUM";
  return "LOW";
}