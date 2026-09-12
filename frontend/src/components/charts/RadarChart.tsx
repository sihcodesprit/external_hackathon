import { palette } from "../../styles/theme";
import type { RadarData, EnsembleDetector } from "../../types";

export function RadarChart({ radar }: { radar: RadarData }) {
  const n = radar.labels.length;
  if (n === 0) return null;
  const cx = 130;
  const cy = 115;
  const R = 82;

  const point = (i: number, v: number) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [cx + Math.cos(angle) * ((v / 100) * R), cy + Math.sin(angle) * ((v / 100) * R)] as const;
  };

  return (
    <svg viewBox="0 0 260 230" width="100%" height={230} style={{ display: "block" }}>
      {[0.25, 0.5, 0.75, 1].map((k) => (
        <polygon
          key={k}
          points={radar.labels.map((_, i) => point(i, k).join(",")).join(" ")}
          fill="none"
          stroke={palette.chartGrid}
          strokeWidth={1}
        />
      ))}
      {radar.labels.map((_, i) => {
        const [x, y] = point(i, 1);
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke={palette.chartGrid} strokeWidth={1} />
            <text
              x={cx + Math.cos((Math.PI * 2 * i) / n - Math.PI / 2) * (R + 26)}
              y={cy + Math.sin((Math.PI * 2 * i) / n - Math.PI / 2) * (R + 26)}
              textAnchor="middle"
              dominantBaseline="middle"
              fill={palette.textDim}
              fontSize={9}
              letterSpacing={0.4}
            >
              {radar.labels[i].split(" ").map(s => s[0]).join("").slice(0, 5).toUpperCase()}
            </text>
          </g>
        );
      })}
      <polygon
        points={radar.labels.map((_, i) => point(i, radar.scores[i] ?? 0).join(",")).join(" ")}
        fill="rgba(34,211,238,0.15)"
        stroke="#22d3ee"
        strokeWidth={1.5}
        style={{ filter: "drop-shadow(0 0 6px rgba(34,211,238,0.3))" }}
      />
      <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fill={palette.textMuted} fontSize={10}>
        DETECTORS
      </text>
    </svg>
  );
}

export function DetectorList({ detectors }: { detectors: EnsembleDetector[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {detectors.map((d) => {
        const flagged = d.is_threat;
        const color = flagged ? palette.danger : palette.good;
        return (
          <div
            key={d.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "7px 10px",
              borderRadius: 7,
              background: flagged ? "rgba(239,68,68,0.06)" : "transparent",
              borderLeft: `2px solid ${color}`,
            }}
          >
            <span style={{ fontSize: 11, color: palette.textDim, width: 14 }}>▮</span>
            <span style={{ flex: 1, fontSize: 12, color: palette.text }}>{d.name}</span>
            <span className="mono" style={{ fontSize: 11, color: palette.textDim }}>
              {((d.score ?? 0) * 100).toFixed(1)}
            </span>
            <span style={{ width: 54, height: 4, background: palette.border, borderRadius: 99, overflow: "hidden" }}>
              <span
                style={{
                  display: "block",
                  height: "100%",
                  width: `${Math.min(100, (d.score ?? 0) * 100).toFixed(0)}%`,
                  background: color,
                }}
              />
            </span>
            <span
              style={{
                width: 56,
                textAlign: "right",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: 0.4,
                color,
              }}
            >
              {flagged ? "FLAGGED" : "clean"}
            </span>
          </div>
        );
      })}
    </div>
  );
}