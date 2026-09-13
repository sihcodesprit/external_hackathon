import { useMemo, useState } from "react";
import { palette, stageColor } from "../../styles/theme";
import type { PredictGraph, PredictGraphEdge, PredictGraphNode } from "../../types";

const NODE_W = 120;
const NODE_H = 84;
const MIN_GAP_X = 150;
const ROW_H = 130;
const PAD = 50;

const reduceMotion =
  typeof window !== "undefined" &&
  !!window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function num(v: unknown, d = 0): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : d;
}

function pct(v: unknown): string {
  const n = Math.min(100, Math.max(0, num(v) * 100));
  return `${Number.isFinite(n) ? Math.round(n) : 0}%`;
}

export function AttackGraphView({
  graph,
  height,
  loading,
  fixedMode,
}: {
  graph?: PredictGraph | null;
  height?: number;
  loading?: boolean;
  fixedMode?: "timeline" | "stages";
}) {
  const [mode, setMode] = useState<"timeline" | "stages">(fixedMode ?? "timeline");
  const [selected, setSelected] = useState<PredictGraphNode | null>(null);

  const activeMode: "timeline" | "stages" = fixedMode ?? mode;

  const data = useMemo(() => {
    if (!graph) return null;
    const nodes = Array.isArray(graph.nodes) ? graph.nodes.length : 0;
    const stageNodes = Array.isArray(graph.stage_nodes) ? graph.stage_nodes.length : 0;
    if (nodes === 0 && stageNodes === 0) return null;

    const timelineNodes: PredictGraphNode[] = (graph.nodes ?? []).filter(
      (n) => n && typeof n.id === "string" && typeof n.label === "string",
    );
    const timelineEdges: PredictGraphEdge[] = (graph.edges ?? []).filter(
      (e) => e && typeof e.source === "string" && typeof e.target === "string",
    );
    const collapsedNodes: PredictGraphNode[] = (graph.stage_nodes ?? []).filter(
      (n) => n && typeof n.id === "string" && typeof n.label === "string",
    );
    const collapsedEdges: PredictGraphEdge[] = (graph.stage_edges ?? []).filter(
      (e) => e && typeof e.source === "string" && typeof e.target === "string",
    );

    const usedNodes = activeMode === "timeline" ? timelineNodes : collapsedNodes;
    const usedEdges = activeMode === "timeline" ? timelineEdges : collapsedEdges;

    const counts = graph.counts ?? {};
    const stages = num(counts.stages, new Set(usedNodes.map((n) => n.stage)).size);
    const transitions = num(counts.transitions, usedEdges.filter((e) => e.transition).length);
    const forecastSteps = num(counts.forecast_steps, Math.max(0, timelineNodes.length - 1));
    const maxRisk = Math.max(0, ...timelineNodes.map((n) => num(n.risk)));

    return {
      usedNodes,
      usedEdges,
      allStages: graph.stages ?? [],
      benignOnly: !!graph.benign_only || (timelineNodes.length > 0 && timelineNodes.every((n) => n.stage === "Benign")),
      unknownStage: !!graph.unknown_stage || timelineNodes.some((n) => n.stage === "Unknown"),
      counts: {
        forecastSteps,
        stages,
        transitions,
        maxRisk,
      },
      rawNodes: timelineNodes,
    };
  }, [graph, activeMode]);

  const layout = useMemo(() => {
    if (!data) return { W: 0, H: 0, pos: new Map<string, { x: number; y: number }>() };
    const pos = new Map<string, { x: number; y: number }>();
    const n = data.usedNodes.length;
    const cols = Math.max(1, Math.ceil(Math.sqrt(n)));
    const rows = Math.ceil(n / cols);
    const W = Math.max(320, cols * MIN_GAP_X + PAD * 2);
    const H = Math.max(140, rows * ROW_H + 20);
    data.usedNodes.forEach((node, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const x = row % 2 === 0
        ? PAD + col * MIN_GAP_X
        : PAD + (cols - 1 - col) * MIN_GAP_X;
      const y = 20 + row * ROW_H + ROW_H / 2;
      pos.set(node.id, { x, y });
    });
    return { W, H, pos };
  }, [data]);

  if (loading) {
    return (
      <div style={{ padding: "28px 16px", display: "flex", flexDirection: "column", gap: 6, alignItems: "center" }}>
        <span className="loading-spinner" style={{ width: 20, height: 20 }} />
        <span style={{ fontSize: 12.5, color: palette.textDim }}>Building predictive attack graph…</span>
        <span style={{ fontSize: 11, color: palette.textMuted }}>Generating forecast stages</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: "26px 16px", display: "flex", flexDirection: "column", gap: 6, alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 650, color: palette.text }}>No predictive attack path available</span>
        <span style={{ fontSize: 11.5, color: palette.textMuted, textAlign: "center", maxWidth: 460 }}>
          The current model output does not contain enough information to construct a stage-transition graph.
        </span>
      </div>
    );
  }

  const { W, H, pos } = layout;
  const svgH = height ?? H;

  const chip = (label: string, value: string | number, color?: string) => (
    <div
      key={label}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "4px 10px", borderRadius: 999, border: `1px solid ${palette.border}`,
        background: "rgba(16,24,42,0.6)", fontSize: 11, color: palette.textDim,
      }}
    >
      <span style={{ color: color ?? palette.accent, fontWeight: 700 }}>{value}</span>
      <span>{label}</span>
    </div>
  );

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {chip("forecast steps", data.counts.forecastSteps)}
          {chip("stage" + (data.counts.stages === 1 ? "" : "s"), data.counts.stages)}
          {chip("transition" + (data.counts.transitions === 1 ? "" : "s"), data.counts.transitions)}
          {chip("max risk", pct(data.counts.maxRisk), palette.danger)}
        </div>
        {!fixedMode && (
          <div style={{ display: "flex", gap: 4, border: `1px solid ${palette.border}`, borderRadius: 999, padding: 3 }}>
            {(["timeline", "stages"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  border: "none", background: activeMode === m ? "rgba(34,211,238,0.16)" : "transparent",
                  color: activeMode === m ? palette.accent : palette.textMuted,
                  fontSize: 11, fontWeight: 600, padding: "3px 12px", borderRadius: 999,
                }}
              >
                {m === "timeline" ? "Timeline" : "Stage Graph"}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 460px", minWidth: 0 }}>
          <svg
            viewBox={`0 0 ${W} ${H}`}
            width="100%"
            height={svgH}
            style={{ display: "block", background: "rgba(10,15,30,0.4)", borderRadius: 10, border: `1px solid ${palette.borderSoft}` }}
          >
            <defs>
              <marker id="pg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={palette.textMuted} />
              </marker>
            </defs>
            {data.usedEdges.map((e, i) => {
              const s = pos.get(e.source);
              const t = pos.get(e.target);
              if (!s || !t) return null;
              const weight = Math.min(0.95, Math.max(0.12, num(e.weight)));
              const w = 1.5 + weight * 3;
              const midX = (s.x + t.x) / 2;
              const midY = (s.y + t.y) / 2 - 12;
              return (
                <g
                  key={e.id ?? `${e.source}->${e.target}#${i}`}
                  className="graph-edge"
                  style={{ transition: reduceMotion ? "none" : "opacity 350ms ease" }}
                >
                  <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke={palette.textMuted} strokeWidth={w} opacity={0.55} markerEnd="url(#pg-arrow)" />
                  <text x={midX} y={midY} textAnchor="middle" fill={palette.textMuted} fontSize={9.5} fontFamily="ui-monospace, monospace">
                    {e.label === "predicted transition" ? "predicted transition" : e.label}
                    {` · conf ${pct(e.weight)}`}
                  </text>
                </g>
              );
            })}
            {data.usedNodes.map((node) => {
              const p = pos.get(node.id);
              if (!p) return null;
              const color = node.type === "current" ? palette.accent : stageColor(node.stage);
              const isSel = selected?.id === node.id;
              const stepLabel = node.step ?? 0;
              return (
                <g
                  key={node.id}
                  className={isSel ? "graph-node graph-node-sel" : "graph-node"}
                  transform={`translate(${p.x - NODE_W / 2}, ${p.y - NODE_H / 2})`}
                  onClick={() => setSelected(node)}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={NODE_W}
                    height={NODE_H}
                    rx={10}
                    fill={`${color}${isSel ? "26" : "14"}`}
                    stroke={isSel ? color : `${color}88`}
                    strokeWidth={isSel ? 2 : 1.5}
                    style={{ filter: `drop-shadow(0 0 ${isSel ? 14 : 6}px ${color}40)` }}
                  />
                  {node.type === "current" && (
                    <text x={NODE_W / 2} y={12} textAnchor="middle" fill={color} fontSize={9} fontWeight={700} fontFamily="ui-monospace, monospace">
                      NOW
                    </text>
                  )}
                  <text x={NODE_W / 2} y={30} textAnchor="middle" fill="#dbe4ff" fontSize={11.5} fontWeight={650}>
                    {node.label}
                  </text>
                  <text x={NODE_W / 2} y={48} textAnchor="middle" fill={palette.textMuted} fontSize={9} fontFamily="ui-monospace, monospace">
                    {stepLabel === 0 ? "current" : `t+${stepLabel}`}
                  </text>
                  <text x={NODE_W / 2} y={66} textAnchor="middle" fill={palette.textDim} fontSize={9}>
                    Risk <tspan fill={node.risk > 0.5 ? palette.danger : palette.text} fontWeight={700}>{pct(node.risk)}</tspan>
                  </text>
                  <text x={NODE_W / 2} y={80} textAnchor="middle" fill={palette.textDim} fontSize={8.5}>
                    Conf {pct(num(node.confidence, node.probability))}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {data.rawNodes.length === 1 && data.rawNodes[0].type === "current" && data.counts.forecastSteps === 0 ? (
          <div style={{ flex: "0 1 240px", minWidth: 220, padding: 12, borderRadius: 10, border: `1px solid ${palette.borderSoft}`, fontSize: 11.5, color: palette.textDim, lineHeight: 1.6 }}>
            No K-step forecast produced yet. The graph will populate once the world model rollout completes.
          </div>
        ) : (
          selected && <NodeDetailPanel node={selected} />
        )}
      </div>

      {data.benignOnly && data.counts.forecastSteps > 0 && (
        <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(52,211,153,0.08)", border: `1px solid rgba(52,211,153,0.3)`, fontSize: 12, color: palette.textDim, lineHeight: 1.6 }}>
          The model does not currently predict a transition into an attack stage.
        </div>
      )}
      {data.unknownStage && (
        <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(251,191,36,0.08)", border: `1px solid rgba(251,191,36,0.35)`, fontSize: 12, color: palette.textDim, lineHeight: 1.6 }}>
          Insufficient evidence — the model could not confidently assign a stage for one or more forecast steps.
        </div>
      )}
    </div>
  );
}

function NodeDetailPanel({ node }: { node: PredictGraphNode }) {
  const color = node.type === "current" ? palette.accent : stageColor(node.stage);
  const evidence = Array.isArray(node.evidence) ? node.evidence.map(String).filter(Boolean) : [];
  return (
    <div
      style={{
        flex: "0 1 240px", minWidth: 220, padding: 14, borderRadius: 10,
        border: `1px solid ${color}55`, background: "rgba(10,15,30,0.6)",
      }}
    >
      <div style={{ fontSize: 12.5, fontWeight: 700, color, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8 }}>
        {node.label}
      </div>
      <DetailRow label="Forecast step" value={node.step === 0 ? "current state" : `t+${node.step}`} />
      <DetailRow label="Risk" value={pct(node.risk)} />
      <DetailRow label="Confidence" value={pct(num(node.confidence, node.probability))} />
      {node.type === "predicted" && (
        <DetailRow label="Stage probability" value={pct(node.probability)} />
      )}
      <div style={{ marginTop: 10, fontSize: 10.5, fontWeight: 700, color: palette.textDim, textTransform: "uppercase", letterSpacing: 0.4 }}>Evidence</div>
      {evidence.length > 0 ? (
        <ul style={{ margin: "6px 0 0", paddingLeft: 14, display: "flex", flexDirection: "column", gap: 4 }}>
          {evidence.map((e, i) => (
            <li key={i} style={{ fontSize: 11, color: palette.textDim, lineHeight: 1.5 }}>{e}</li>
          ))}
        </ul>
      ) : (
        <div style={{ marginTop: 6, fontSize: 11, color: palette.textMuted }}>No supporting feature evidence emitted for this step.</div>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "3px 0", fontSize: 11.5 }}>
      <span style={{ color: palette.textDim }}>{label}</span>
      <span className="mono" style={{ color: palette.text, fontWeight: 600 }}>{value}</span>
    </div>
  );
}