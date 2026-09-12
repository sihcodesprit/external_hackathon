import { palette } from "../../styles/theme";
import type { PredictGraph } from "../../types";
import { stageColor } from "../../styles/theme";

export function AttackGraphView({ graph }: { graph: PredictGraph }) {
  const nodes = graph.nodes ?? [];
  const edges = graph.edges ?? [];
  if (nodes.length === 0) {
    return <div style={{ fontSize: 12, color: palette.textMuted, padding: 20 }}>No predicted transitions yet.</div>;
  }

  const W = 760;
  const H = 240;
  const order = nodes.map((n, i) => ({
    ...n,
    customStep: n.step ?? (n.type === "current" ? 0 : i + 1),
  }));
  const positions = layoutNodes(order, W, H);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: "block", overflow: "visible" }}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={palette.border} />
        </marker>
      </defs>
      {edges.map((e, i) => {
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return null;
        const midX = (s.x + t.x) / 2;
        const midY = (s.y + t.y) / 2 - 14;
        return (
          <g key={i}>
            <line
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke={palette.border}
              strokeWidth={Math.max(1, e.weight * 5)}
              opacity={0.55}
              markerEnd="url(#arrow)"
            />
            <text x={midX} y={midY} textAnchor="middle" fill={palette.textMuted} fontSize={9.5} fontFamily="ui-monospace, monospace">
              {e.label}
            </text>
          </g>
        );
      })}
      {nodes.map((n, i) => {
        const p = positions[n.id];
        const color = n.type === "current" ? palette.accent : stageColor(n.stage);
        const r = n.type === "current" ? 30 : 22;
        return (
          <g key={n.id} transform={`translate(${p.x}, ${p.y})`}>
            <circle r={r} fill={`${color}14`} stroke={color} strokeWidth={2} style={{ filter: `drop-shadow(0 0 8px ${color}50)` }} />
            {n.type === "current" && (
              <circle r={r + 7} fill="none" stroke={color} strokeWidth={1} opacity={0.35} />
            )}
            <text y={-3} textAnchor="middle" fill="#dbe4ff" fontSize={10} fontWeight={650} fontFamily="ui-monospace, monospace">
              {n.step ?? (n.type === "current" ? 0 : i + 1)}
            </text>
            <text y={10} textAnchor="middle" fill={palette.textDim} fontSize={6.5}>
              risk {(n.risk ?? 0).toFixed(1)}
            </text>
            <text
              x={r + 10}
              y={-4}
              textAnchor="start"
              fill={color}
              fontSize={11.5}
              fontWeight={600}
            >
              {n.label}
            </text>
            <text x={r + 10} y={9} textAnchor="start" fill={palette.textMuted} fontSize={9.5}>
              p = {(n.probability ?? 0).toFixed(2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function layoutNodes(nodes: Array<{ id: string; customStep?: number }>, W: number, H: number) {
  const pos: Record<string, { x: number; y: number }> = {};
  const steps = nodes.map((n) => Math.round(n.customStep ?? 0));
  const max = Math.max(1, ...steps);
  nodes.forEach((n, i) => {
    const s = Math.round(n.customStep ?? 0);
    const x = 70 + (s / max) * (W - 140);
    const y = H / 2 + ((i % 3) - 1) * 58;
    pos[n.id] = { x, y };
  });
  return pos;
}