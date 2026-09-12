import { palette } from "../../styles/theme";
import type { FeatureAttribution } from "../../types";

export function FeatureBars({ features, color = "#22d3ee", max }: {
  features: FeatureAttribution[];
  color?: string;
  max?: number;
}) {
  const items = features.slice(0, 12);
  const maxAbs = max ?? Math.max(0.0001, ...items.map((f) => Math.abs(f.contribution ?? 0)));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {items.map((f) => {
        const v = f.contribution ?? 0;
        const w = (Math.abs(v) / maxAbs) * 100;
        const neg = v < 0;
        return (
          <div key={f.feature} style={{ display: "grid", gridTemplateColumns: "1fr 120px 56px", gap: 8, alignItems: "center" }}>
            <span
              style={{
                fontSize: 11.5,
                color: palette.textDim,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={`${f.feature}: ${f.description ?? ""}`}
            >
              {f.feature}
            </span>
            <div style={{ position: "relative", height: 9, background: palette.border, borderRadius: 4 }}>
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  height: "100%",
                  width: `${w}%`,
                  borderRadius: 4,
                  background: neg ? "#f87171" : color,
                  opacity: 0.85,
                }}
              />
            </div>
            <span className="mono" style={{ fontSize: 10.5, color: neg ? palette.danger : palette.textDim, textAlign: "right" }}>
              {v >= 0 ? "+" : "−"}{Math.abs(v).toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}