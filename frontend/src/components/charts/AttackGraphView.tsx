import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { palette, stageColor } from "../../styles/theme";
import type { PredictGraph, PredictGraphEdge, PredictGraphNode } from "../../types";

const CARD_W = 176;
const CARD_H = 98;
const COL_GAP = 216;
const V_GAP = 30;
const PAD_L = 48;
const PAD_T = 52;
const PAD_R = 48;
const PAD_B = 48;
const MIN_H = 340;

const reduceMotion =
  typeof window !== "undefined" &&
  !!window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function num(v: unknown, d = 0): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : d;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Convert a backend risk/confidence value to a 0-100 percentage. The backend
 * emits fractions (0..1); older payloads may emit 0..100. Values ≤ 1 (and > 0)
 * are treated as a fraction so percentages are never inflated to 10000%. */
function toPct(v: unknown): number {
  const n = num(v);
  const pct = n > 0 && n <= 1 ? n * 100 : n;
  return clamp(Number.isFinite(pct) ? pct : 0, 0, 100);
}

function pctStr(v: unknown): string {
  return `${Math.round(toPct(v))}%`;
}

type PosNode = PredictGraphNode & { x: number; y: number };

interface LayoutEdge {
  key: string;
  edge: PredictGraphEdge;
  source: PosNode;
  target: PosNode;
}

interface LayoutModel {
  W: number;
  H: number;
  nodes: PosNode[];
  edges: LayoutEdge[];
  forecastSteps: number;
  stages: number;
  transitions: number;
  maxRisk: number;
}

/** Deterministic horizontal timeline: group nodes by forecast step, one column
 * per step, ordered left→right from NOW (t0) through t+k. Columns with multiple
 * nodes stack vertically so nothing zigzags or overlaps. */
function buildTimelineColumns(nodes: PredictGraphNode[]): PredictGraphNode[][] {
  const byStep = new Map<number, PredictGraphNode[]>();
  for (const n of nodes) {
    const s = Math.max(0, Math.floor(num(n.step, 0)));
    const arr = byStep.get(s) ?? [];
    arr.push(n);
    byStep.set(s, arr);
  }
  const keys = [...byStep.keys()].sort((a, b) => a - b);
  return keys.map((k) => byStep.get(k) ?? []);
}

/** Deterministic stage-chain ordering: topological order (Kahn) with stable
 * tie-breaking, falling back to original order for disconnected/cyclic nodes. */
function orderStageNodes(nodes: PredictGraphNode[], edges: PredictGraphEdge[]): PredictGraphNode[] {
  const indeg = new Map<string, number>();
  const adj = new Map<string, string[]>();
  for (const n of nodes) {
    indeg.set(n.id, 0);
    adj.set(n.id, []);
  }
  for (const e of edges) {
    if (!indeg.has(e.source) || !indeg.has(e.target)) continue;
    adj.get(e.source)?.push(e.target);
    indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1);
  }
  const queue: string[] = nodes
    .filter((n) => (indeg.get(n.id) ?? 0) === 0)
    .map((n) => n.id)
    .sort();
  const out: string[] = [];
  const seen = new Set<string>();
  while (queue.length) {
    const id = queue.shift() ?? "";
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(id);
    const next: string[] = [];
    for (const t of adj.get(id) ?? []) {
      if (seen.has(t)) continue;
      indeg.set(t, (indeg.get(t) ?? 1) - 1);
      if (indeg.get(t) === 0) next.push(t);
    }
    next.sort();
    queue.unshift(...next);
  }
  for (const n of nodes) if (!seen.has(n.id)) out.push(n.id);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  return out.map((id) => byId.get(id)).filter((n): n is PredictGraphNode => !!n);
}

function sortCol(col: PredictGraphNode[]): PredictGraphNode[] {
  return [...col].sort(
    (a, b) =>
      num(b.severity) - num(a.severity) ||
      toPct(b.risk) - toPct(a.risk) ||
      String(a.id).localeCompare(String(b.id)),
  );
}

function bezier(path: { source: PosNode; target: PosNode }): {
  d: string;
  mid: { x: number; y: number };
} {
  const a = { x: path.source.x + CARD_W / 2, y: path.source.y };
  const b = { x: path.target.x - CARD_W / 2, y: path.target.y };
  const dx = clamp(Math.abs(b.x - a.x) * 0.5, 40, 170);
  const d = `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
  const mx = (a.x + 3 * (a.x + dx) + 3 * (b.x - dx) + b.x) / 8;
  const my = (a.y + 3 * a.y + 3 * b.y + b.y) / 8;
  return { d, mid: { x: mx, y: my } };
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
  const [view, setView] = useState<{ s: number; x: number; y: number }>({ s: 1, x: 0, y: 0 });
  const [box, setBox] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [dragging, setDragging] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const touched = useRef(false);
  const drag = useRef<{ startX: number; startY: number; vx: number; vy: number } | null>(null);
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");

  const activeMode: "timeline" | "stages" = fixedMode ?? mode;

  const model = useMemo<LayoutModel | null>(() => {
    if (!graph) return null;
    const timelineNodes = (graph.nodes ?? []).filter(
      (n) => n && typeof n.id === "string" && typeof n.label === "string",
    );
    const timelineEdges = (graph.edges ?? []).filter(
      (e) => e && typeof e.source === "string" && typeof e.target === "string",
    );
    const stageNodes = (graph.stage_nodes ?? []).filter(
      (n) => n && typeof n.id === "string" && typeof n.label === "string",
    );
    const stageEdges = (graph.stage_edges ?? []).filter(
      (e) => e && typeof e.source === "string" && typeof e.target === "string",
    );

    const usingTimeline = activeMode === "timeline";
    const usedEdges = usingTimeline ? timelineEdges : stageEdges;

    let cols: PredictGraphNode[][];
    if (usingTimeline) {
      cols = buildTimelineColumns(timelineNodes);
      if (cols.length === 0 && stageNodes.length) cols = stageNodes.map((n) => [n]);
    } else {
      cols = orderStageNodes(stageNodes.length ? stageNodes : timelineNodes, stageEdges).map(
        (n) => [n],
      );
    }
    if (cols.length === 0) return null;
    cols = cols.map(sortCol);

    const colCount = cols.length;
    const maxInCol = Math.max(...cols.map((c) => c.length), 1);
    const H = Math.max(MIN_H, PAD_T + PAD_B + maxInCol * CARD_H + (maxInCol - 1) * V_GAP);
    const W = PAD_L + (colCount - 1) * COL_GAP + CARD_W + PAD_R;
    const centerY = H / 2;

    const pos = new Map<string, PosNode>();
    cols.forEach((col, ci) => {
      const n = col.length;
      const x = PAD_L + ci * COL_GAP + CARD_W / 2;
      col.forEach((node, ri) => {
        const y = centerY + (ri - (n - 1) / 2) * (CARD_H + V_GAP);
        pos.set(node.id, { ...node, x, y });
      });
    });

    const edges: LayoutEdge[] = usedEdges
      .map((e) => ({ edge: e, source: pos.get(e.source), target: pos.get(e.target) }))
      .filter(
        (x): x is { edge: PredictGraphEdge; source: PosNode; target: PosNode } =>
          !!x.source && !!x.target,
      )
      .map(({ edge, source, target }, i) => ({
        key: edge.id ?? `${edge.source}->${edge.target}#${i}`,
        edge,
        source,
        target,
      }))
      .sort((a, b) => a.source.x - b.source.x || a.target.x - b.target.x);

    const counts = graph.counts ?? {};
    const nodes = [...pos.values()];
    return {
      W,
      H,
      nodes,
      edges,
      forecastSteps: num(counts.forecast_steps, Math.max(0, timelineNodes.length - 1)),
      stages: num(counts.stages, cols.length),
      transitions: num(counts.transitions, edges.filter((e) => e.edge.transition).length),
      maxRisk: Math.max(0, ...nodes.map((p) => num(p.risk))),
    };
  }, [graph, activeMode]);

  const fitView = useCallback(
    (w: number, h: number, m: LayoutModel | null) => {
      if (!m || w <= 0 || h <= 0) return null;
      const s = clamp(Math.min((w - 24) / m.W, (h - 24) / m.H), 0.15, 1.5);
      return { s, x: (w - m.W * s) / 2, y: (h - m.H * s) / 2 };
    },
    [],
  );

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (!rect) return;
      setBox({ w: rect.width, h: rect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // New graph or mode → reset interaction state and refit.
  useEffect(() => {
    touched.current = false;
    setSelected(null);
    setView({ s: 1, x: 0, y: 0 });
  }, [graph, activeMode]);

  // Auto-fit whenever the layout or container box changes (until the user pans/zooms).
  useEffect(() => {
    if (!model || touched.current) return;
    const f = fitView(box.w, box.h, model);
    if (f) setView(f);
  }, [model, box, fitView]);

  const zoomAt = (factor: number) => {
    touched.current = true;
    setView((v) => {
      const cx = box.w / 2;
      const cy = box.h / 2;
      const wx = (cx - v.x) / v.s;
      const wy = (cy - v.y) / v.s;
      const ns = clamp(v.s * factor, 0.2, 3.5);
      return { s: ns, x: cx - wx * ns, y: cy - wy * ns };
    });
  };

  const doFit = () => {
    touched.current = true;
    const f = fitView(box.w, box.h, model);
    if (f) setView(f);
  };

  const doReset = () => {
    touched.current = false;
    const f = fitView(box.w, box.h, model);
    if (f) setView(f);
  };

  const onPointerDown = (e: React.PointerEvent) => {
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    drag.current = { startX: e.clientX, startY: e.clientY, vx: view.x, vy: view.y };
    setDragging(true);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    touched.current = true;
    setView((v) => ({
      ...v,
      x: drag.current!.vx + (e.clientX - drag.current!.startX),
      y: drag.current!.vy + (e.clientY - drag.current!.startY),
    }));
  };
  const onPointerUp = () => {
    if (drag.current) {
      drag.current = null;
      setDragging(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "28px 16px", display: "flex", flexDirection: "column", gap: 6, alignItems: "center" }}>
        <span className="loading-spinner" style={{ width: 20, height: 20 }} />
        <span style={{ fontSize: 12.5, color: palette.textDim }}>Building predictive attack graph…</span>
        <span style={{ fontSize: 11, color: palette.textMuted }}>Generating forecast stages</span>
      </div>
    );
  }

  if (!model) {
    return (
      <div style={{ padding: "26px 16px", display: "flex", flexDirection: "column", gap: 6, alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 650, color: palette.text }}>No predictive attack path available</span>
        <span style={{ fontSize: 11.5, color: palette.textMuted, textAlign: "center", maxWidth: 460 }}>
          The current model output does not contain enough information to construct a stage-transition graph.
        </span>
      </div>
    );
  }

  const benignOnly =
    !!graph?.benign_only ||
    model.nodes.every((p) => String(p.stage).toLowerCase().startsWith("benign"));
  const unknownStage =
    !!graph?.unknown_stage || model.nodes.some((p) => String(p.stage).toLowerCase() === "unknown");
  const boxHeight = typeof height === "number" && height > 0 ? `${height}px` : "clamp(500px, 62vh, 760px)";
  const minBoxHeight = typeof height === "number" && height > 0 ? undefined : 500;

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

  const zoomBtnStyle = {
    border: `1px solid ${palette.border}`,
    background: "rgba(16,24,42,0.7)",
    color: palette.textDim,
    fontSize: 12,
    lineHeight: 1,
    padding: "6px 9px",
    borderRadius: 7,
    cursor: "pointer",
  } as const;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {chip("forecast steps", model.forecastSteps)}
          {chip("stage" + (model.stages === 1 ? "" : "s"), model.stages)}
          {chip("transition" + (model.transitions === 1 ? "" : "s"), model.transitions)}
          {chip("max risk", pctStr(model.maxRisk), palette.danger)}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {!fixedMode && (
            <div style={{ display: "flex", gap: 4, border: `1px solid ${palette.border}`, borderRadius: 999, padding: 3 }}>
              {(["timeline", "stages"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  style={{
                    border: "none", background: activeMode === m ? "rgba(34,211,238,0.16)" : "transparent",
                    color: activeMode === m ? palette.accent : palette.textMuted,
                    fontSize: 11, fontWeight: 600, padding: "3px 12px", borderRadius: 999, cursor: "pointer",
                  }}
                >
                  {m === "timeline" ? "Timeline" : "Stage Graph"}
                </button>
              ))}
            </div>
          )}
          <div style={{ display: "flex", gap: 4 }}>
            <button type="button" aria-label="Zoom out" style={zoomBtnStyle} onClick={() => zoomAt(0.82)}>−</button>
            <span className="mono" style={{ fontSize: 10.5, color: palette.textMuted, minWidth: 42, textAlign: "center", alignSelf: "center" }}>
              {Math.round(view.s * 100)}%
            </span>
            <button type="button" aria-label="Zoom in" style={zoomBtnStyle} onClick={() => zoomAt(1.22)}>+</button>
            <button type="button" aria-label="Fit graph to view" style={zoomBtnStyle} onClick={doFit}>Fit</button>
            <button type="button" aria-label="Reset zoom" style={zoomBtnStyle} onClick={doReset}>Reset</button>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div
          ref={wrapRef}
          className="pagn-viewport"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onClick={() => setSelected(null)}
          style={{
            flex: "1 1 460px",
            minWidth: 0,
            height: boxHeight,
            minHeight: minBoxHeight,
            position: "relative",
            overflow: "hidden",
            background: "rgba(10,15,30,0.4)",
            borderRadius: 10,
            border: `1px solid ${palette.borderSoft}`,
            cursor: dragging ? "grabbing" : "grab",
            userSelect: "none",
            touchAction: "none",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})`,
              transformOrigin: "0 0",
              width: model.W,
              height: model.H,
            }}
          >
            <svg
              width={model.W}
              height={model.H}
              style={{ position: "absolute", left: 0, top: 0, overflow: "visible", display: "block" }}
            >
              <defs>
                <marker
                  id={`pagn-arrow-${uid}`}
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="6.5"
                  markerHeight="6.5"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill={palette.accent} />
                </marker>
              </defs>
              {model.edges.map((le) => {
                const { d } = bezier(le);
                const weight = clamp(num(le.edge.weight), 0, 1);
                const w = 1.5 + weight * 2.5;
                const isPredicted = le.edge.transition || String(le.edge.label).includes("predicted");
                return (
                  <path
                    key={le.key}
                    className="pagn-edge"
                    d={d}
                    fill="none"
                    stroke={isPredicted ? "#22d3ee" : palette.textMuted}
                    strokeWidth={w}
                    strokeOpacity={0.45}
                    markerEnd={`url(#pagn-arrow-${uid})`}
                  />
                );
              })}
            </svg>

            {model.edges.map((le) => {
              const { mid } = bezier(le);
              const labelRaw = String(le.edge.label ?? "transition");
              const label = labelRaw.length > 18 ? `${labelRaw.slice(0, 18)}…` : labelRaw;
              return (
                <div
                  key={le.key}
                  style={{
                    position: "absolute",
                    left: mid.x,
                    top: mid.y - 12,
                    transform: "translate(-50%,-50%)",
                    background: "rgba(13,20,37,0.96)",
                    border: `1px solid ${palette.borderSoft}`,
                    borderRadius: 999,
                    padding: "2px 8px",
                    fontSize: 9.5,
                    color: palette.textMuted,
                    whiteSpace: "nowrap",
                    maxWidth: 170,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    pointerEvents: "none",
                    zIndex: 1,
                  }}
                >
                  {label} · conf {pctStr(le.edge.weight)}
                </div>
              );
            })}

            {model.nodes.map((p, i) => {
              const color = p.type === "current" ? palette.accent : stageColor(p.stage);
              const stepLabel = num(p.step, 0);
              const riskPct = toPct(p.risk);
              const confPct = toPct(num(p.confidence, p.probability));
              const evidenceCount = Array.isArray(p.evidence) ? p.evidence.filter(Boolean).length : 0;
              const isSel = selected?.id === p.id;
              return (
                <div
                  key={p.id}
                  className={isSel ? "pagn-card pagn-sel" : "pagn-card"}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelected(p);
                  }}
                  title={`${p.label}\nRisk ${pctStr(p.risk)} · Confidence ${pctStr(num(p.confidence, p.probability))}`}
                  style={{
                    position: "absolute",
                    left: p.x - CARD_W / 2,
                    top: p.y - CARD_H / 2,
                    width: CARD_W,
                    height: CARD_H,
                    boxSizing: "border-box",
                    background: "rgba(10,15,30,0.92)",
                    border: `1px solid ${color}66`,
                    borderLeft: `3px solid ${color}`,
                    borderRadius: 10,
                    padding: "9px 11px",
                    cursor: "pointer",
                    animationDelay: reduceMotion ? "0ms" : `${i * 55}ms`,
                    zIndex: 2,
                    boxShadow: isSel
                      ? `0 0 0 1px ${color}66, 0 12px 30px rgba(0,0,0,0.5)`
                      : "0 6px 18px rgba(0,0,0,0.35)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        fontSize: 9, fontWeight: 700, letterSpacing: 0.6,
                        color, background: `${color}1f`, border: `1px solid ${color}44`,
                        borderRadius: 5, padding: "1px 6px",
                      }}
                    >
                      {p.type === "current" || stepLabel === 0 ? "NOW" : `t+${stepLabel}`}
                    </span>
                    <span style={{ marginLeft: "auto", fontSize: 10, color: palette.textMuted }}>
                      {evidenceCount > 0 ? `${evidenceCount} ev` : ""}
                    </span>
                  </div>
                  <div
                    style={{
                      marginTop: 6,
                      fontSize: 12.5,
                      fontWeight: 700,
                      lineHeight: 1.22,
                      color: "#dbe4ff",
                      maxHeight: 32,
                      overflow: "hidden",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                    }}
                  >
                    {p.label}
                  </div>
                  <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ flex: 1, height: 4, borderRadius: 99, background: palette.border, overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${riskPct}%`,
                          borderRadius: 99,
                          background: riskPct >= 75 ? palette.danger : riskPct >= 50 ? palette.warn : palette.good,
                          transition: reduceMotion ? "none" : "width 400ms ease",
                        }}
                      />
                    </div>
                    <span className="mono" style={{ fontSize: 10, color: palette.textDim }}>
                      {Math.round(riskPct)}%
                    </span>
                  </div>
                  <div style={{ marginTop: 5, display: "flex", justifyContent: "space-between", fontSize: 10, color: palette.textMuted }}>
                    <span>conf {Math.round(confPct)}%</span>
                    <span>sev {num(p.severity, 0).toFixed(1)}</span>
                  </div>
                </div>
              );
            })}
          </div>

          <div
            className="mono"
            style={{
              position: "absolute",
              left: 8,
              bottom: 8,
              fontSize: 10,
              color: palette.textMuted,
              background: "rgba(13,20,37,0.7)",
              border: `1px solid ${palette.borderSoft}`,
              borderRadius: 6,
              padding: "2px 7px",
              pointerEvents: "none",
            }}
          >
            drag to pan · wheel disabled · zoom {Math.round(view.s * 100)}%
          </div>
        </div>

        {model.nodes.length === 1 && model.nodes[0].type === "current" && model.forecastSteps === 0 ? (
          <div style={{ flex: "0 1 240px", minWidth: 220, padding: 12, borderRadius: 10, border: `1px solid ${palette.borderSoft}`, fontSize: 11.5, color: palette.textDim, lineHeight: 1.6 }}>
            No K-step forecast produced yet. The graph will populate once the world model rollout completes.
          </div>
        ) : selected ? (
          <NodeDetailPanel node={selected} />
        ) : null}
      </div>

      {benignOnly && model.forecastSteps > 0 && (
        <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.3)", fontSize: 12, color: palette.textDim, lineHeight: 1.6 }}>
          The model does not currently predict a transition into an attack stage.
        </div>
      )}
      {unknownStage && (
        <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.35)", fontSize: 12, color: palette.textDim, lineHeight: 1.6 }}>
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
      <DetailRow label="Risk" value={pctStr(node.risk)} />
      <DetailRow label="Confidence" value={pctStr(num(node.confidence, node.probability))} />
      {node.type === "predicted" && <DetailRow label="Stage probability" value={pctStr(node.probability)} />}
      <div style={{ marginTop: 10, fontSize: 10.5, fontWeight: 700, color: palette.textDim, textTransform: "uppercase", letterSpacing: 0.4 }}>
        Evidence
      </div>
      {evidence.length > 0 ? (
        <ul style={{ margin: "6px 0 0", paddingLeft: 14, display: "flex", flexDirection: "column", gap: 4 }}>
          {evidence.map((e, i) => (
            <li key={i} style={{ fontSize: 11, color: palette.textDim, lineHeight: 1.5 }}>{e}</li>
          ))}
        </ul>
      ) : (
        <div style={{ marginTop: 6, fontSize: 11, color: palette.textMuted }}>
          No supporting feature evidence emitted for this step.
        </div>
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