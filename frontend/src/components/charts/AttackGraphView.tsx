import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { palette, stageColor } from "../../styles/theme";
import type { PredictGraph, PredictGraphEdge, PredictGraphNode } from "../../types";

/* ── Geometry ───────────────────────────────────────────────────────────
 * Cards are 210×124 with a permanent ≥132px horizontal corridor between
 * them. The corridor is where edges, arrows and their compact labels live,
 * so nothing edge-related can physically overlap a node card. */
const CARD_W = 210;
const CARD_H = 124;
const COL_GAP = CARD_W + 132; // node-centre spacing → ~132px free between cards
const V_GAP = 36;
const PAD_L = 84;
const PAD_T = 72;
const PAD_R = 84;
const PAD_B = 72;
const MIN_H = 380;

/* Zoom clamps: never shrink so far that card text becomes unreadable —
 * if the graph is wider than the viewport, the viewport scrolls instead. */
const MIN_SCALE = 0.55;
const MAX_SCALE = 1.6;

function num(v: unknown, d = 0): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : d;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Backend risks/confidences are fractions (0..1); some payloads emit 0..100.
 * Values > 0 and <= 1 are treated as fractions so percentages are never
 * inflated to 10000%. */
function toPct(v: unknown): number {
  const n = num(v);
  const pct = n > 0 && n <= 1 ? n * 100 : n;
  return clamp(Number.isFinite(pct) ? pct : 0, 0, 100);
}

function pctStr(v: unknown): string {
  return `${Math.round(toPct(v))}%`;
}

function finitePt(v: number | undefined | null): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

type PosNode = PredictGraphNode & { x: number; y: number };

interface LayoutEdge {
  key: string;
  edge: PredictGraphEdge;
  source: PosNode;
  target: PosNode;
  lane: number; // perpendicular spacing for parallel edges
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

interface Rect2D {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/* ── Deterministic layout ─────────────────────────────────────────────── */

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

/* Edge geometry: connects right-centre of source → left-centre of target,
 * arrow marker terminates exactly at the target card boundary. y-bend is
 * added per lane so parallel edges fan out instead of stacking on one line. */
function bezier(le: LayoutEdge): { d: string; mid: { x: number; y: number }; slope: number } {
  const a = { x: le.source.x + CARD_W / 2, y: le.source.y + le.lane * 22 };
  const b = { x: le.target.x - CARD_W / 2, y: le.target.y + le.lane * 22 };
  const dx = clamp(Math.abs(b.x - a.x) * 0.5, 50, 150);
  const d = `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
  const mx = (a.x + 3 * (a.x + dx) + 3 * (b.x - dx) + b.x) / 8;
  const my = (a.y + 3 * a.y + 3 * b.y + b.y) / 8;
  const slope = b.y !== a.y ? Math.atan2(b.y - a.y, b.x - a.x) : 0;
  return { d, mid: { x: mx, y: my }, slope };
}

/* Label collision avoidance: propose candidate anchor points (always OUTSIDE
 * and above/below the edge corridor, clear of the source/target card bodies)
 * and return the first one whose pill box does not intersect any node card. */
function pickLabelPos(
  base: { x: number; y: number },
  w: number,
  h: number,
  rects: Rect2D[],
): { x: number; y: number } {
  const candidates = [
    { x: base.x, y: base.y - 24 },
    { x: base.x, y: base.y - 44 },
    { x: base.x, y: base.y + 22 },
    { x: base.x, y: base.y + 42 },
    { x: base.x - 46, y: base.y - 24 },
    { x: base.x + 46, y: base.y - 24 },
    { x: base.x - 80, y: base.y },
    { x: base.x + 80, y: base.y },
  ];
  const hits = (p: { x: number; y: number }) =>
    rects.some(
      (r) =>
        p.x + w / 2 > r.x0 - 6 &&
        p.x - w / 2 < r.x1 + 6 &&
        p.y + h / 2 > r.y0 - 6 &&
        p.y - h / 2 < r.y1 + 6,
    );
  return candidates.find((c) => !hits(c)) ?? { x: base.x, y: base.y - 44 };
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
  const [selectedNode, setSelectedNode] = useState<PredictGraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<LayoutEdge | null>(null);
  const [view, setView] = useState<{ s: number; x: number; y: number }>({ s: 1, x: 0, y: 0 });
  const [box, setBox] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [laySig, setLaySig] = useState(0);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef(view);
  const boxRef = useRef(box);
  const modelRef = useRef<LayoutModel | null>(null);
  const touched = useRef(false);
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    viewRef.current = view;
  }, [view]);
  useEffect(() => {
    boxRef.current = box;
  }, [box]);

  const activeMode: "timeline" | "stages" = fixedMode ?? mode;

  const model = useMemo<LayoutModel | null>(() => {
    if (!graph) return null;
    const timelineNodes = (graph.nodes ?? []).filter(
      (n) =>
        n &&
        typeof n.id === "string" &&
        typeof n.label === "string" &&
        finitePt(n.risk) &&
        Number.isFinite(finitePt(n.confidence) ? n.confidence : 0),
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
    const centerY = PAD_T + ((maxInCol - 1) * (CARD_H + V_GAP)) / 2 + CARD_H / 2;

    const pos = new Map<string, PosNode>();
    cols.forEach((col, ci) => {
      const n = col.length;
      const x = PAD_L + ci * COL_GAP + CARD_W / 2;
      col.forEach((node, ri) => {
        const y = centerY + (ri - (n - 1) / 2) * (CARD_H + V_GAP);
        pos.set(node.id, { ...node, x, y });
      });
    });

    // Parallel edges (same source AND target) get a lane so they fan out.
    const pairCount = new Map<string, number>();
    for (const e of usedEdges) {
      if (pos.has(e.source) && pos.has(e.target)) {
        const k = e.source === e.target ? e.source : `${e.source}\u0000${e.target}`;
        pairCount.set(k, (pairCount.get(k) ?? 0) + 1);
      }
    }
    const seen = new Map<string, number>();
    const edges: LayoutEdge[] = usedEdges
      .map((e) => ({ edge: e, source: pos.get(e.source), target: pos.get(e.target) }))
      .filter(
        (x): x is { edge: PredictGraphEdge; source: PosNode; target: PosNode } =>
          !!x.source && !!x.target,
      )
      .map(({ edge, source, target }) => {
        const k = source.id === target.id ? source.id : `${source.id}\u0000${target.id}`;
        const idx = seen.get(k) ?? 0;
        seen.set(k, idx + 1);
        const total = pairCount.get(k) ?? 1;
        const lane = total > 1 ? idx - (total - 1) / 2 : 0;
        return { key: edge.id ?? `${edge.source}->${edge.target}#${idx}`, edge, source, target, lane };
      })
      .sort((a, b) => a.source.x - b.source.x || a.lane - b.lane || a.target.x - b.target.x);

    const counts = graph.counts ?? {};
    const nodes = [...pos.values()];
    const maxRisk = Math.max(0, ...nodes.map((p) => num(p.risk)));
    return {
      W,
      H,
      nodes,
      edges,
      forecastSteps: num(counts.forecast_steps, Math.max(0, timelineNodes.length - 1)),
      stages: num(counts.stages, cols.length),
      transitions: num(counts.transitions, edges.filter((e) => e.edge.transition).length),
      maxRisk: Number.isFinite(maxRisk) ? maxRisk : 0,
    };
  }, [graph, activeMode]);

  useEffect(() => {
    modelRef.current = model;
  }, [model]);

  /* Recompute fit whenever data/mode changes; user zoom (touched) is preserved
   * across viewport resizes. */
  const fitView = useCallback((m: LayoutModel | null, w: number, h: number) => {
    if (!m || w <= 0 || h <= 0) return null;
    const s = clamp(Math.min((w - 28) / m.W, (h - 28) / m.H), MIN_SCALE, MAX_SCALE);
    const x = (w - m.W * s) / 2;
    const y = (h - m.H * s) / 2;
    return {
      s,
      x: m.W * s > w ? 0 : Math.max(0, x),
      y: m.H * s > h ? 0 : Math.max(0, y),
    };
  }, []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (!rect) return;
      boxRef.current = { w: rect.width, h: rect.height };
      setBox({ w: rect.width, h: rect.height });
      if (!touched.current) {
        const f = fitView(modelRef.current, rect.width, rect.height);
        if (f) setView(f);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fitView]);

  const zoomAt = useCallback((factor: number) => {
    touched.current = true;
    const b = boxRef.current;
    setView((cur) => {
      const cx = b.w / 2;
      const cy = b.h / 2;
      const wx = (cx - cur.x) / cur.s;
      const wy = (cy - cur.y) / cur.s;
      const ns = clamp(cur.s * factor, MIN_SCALE, MAX_SCALE);
      return { s: ns, x: cx - wx * ns, y: cy - wy * ns };
    });
  }, []);

  const doFit = useCallback(() => {
    touched.current = false;
    const f = fitView(modelRef.current, boxRef.current.w, boxRef.current.h);
    if (f) setView(f);
  }, [fitView]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      zoomAt(e.deltaY < 0 ? 1.12 : 0.89);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  // New graph or mode → reset selection and re-run the one-shot layout animation.
  useEffect(() => {
    touched.current = false;
    setSelectedNode(null);
    setSelectedEdge(null);
    setLaySig((k) => k + 1);
    const f = fitView(modelRef.current, boxRef.current.w, boxRef.current.h);
    if (f) setView(f);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, activeMode]);

  if (loading) {
    return (
      <div style={{ padding: "28px 16px", display: "flex", flexDirection: "column", gap: 6, alignItems: "center" }}>
        <span className="loading-spinner" style={{ width: 20, height: 20 }} />
        <span style={{ fontSize: 12.5, color: palette.textDim }}>Building predictive attack graph…</span>
        <span style={{ fontSize: 11, color: palette.textMuted }}>Generating forecast stages</span>
      </div>
    );
  }

  if (!model || model.nodes.length === 0) {
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

  // The scrollable content box must exactly bound the rendered graph so every
  // part of it (including negative translate offsets from center-zoom) stays
  // reachable and no phantom scrollable space appears past its edges.
  const cw = Math.max(model.W * view.s, view.x + model.W * view.s);
  const ch = Math.max(model.H * view.s, view.y + model.H * view.s);
  const layerL = -Math.min(0, view.x);
  const layerT = -Math.min(0, view.y);
  const boxHeight = typeof height === "number" && height > 0 ? `${height}px` : "clamp(500px, 62vh, 760px)";
  const minBoxHeight = typeof height === "number" && height > 0 ? undefined : 500;

  // Node bounding boxes (used for edge-label collision avoidance).
  const rects: Rect2D[] = model.nodes.map((p) => ({
    x0: p.x - CARD_W / 2,
    y0: p.y - CARD_H / 2,
    x1: p.x + CARD_W / 2,
    y1: p.y + CARD_H / 2,
  }));

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
          <div
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "4px 10px", borderRadius: 999, border: `1px solid ${palette.border}`,
              background: "rgba(16,24,42,0.6)", fontSize: 11, color: palette.textDim,
            }}
          >
            <span style={{ width: 14, height: 0, borderTop: `2px solid ${palette.accent}`, display: "inline-block" }} />
            <span>predicted transition</span>
          </div>
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
            <button type="button" aria-label="Reset view" style={zoomBtnStyle} onClick={doFit}>Reset</button>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div
          ref={wrapRef}
          className="pagn-viewport"
          onClick={() => {
            setSelectedNode(null);
            setSelectedEdge(null);
          }}
          style={{
            flex: "1 1 460px",
            minWidth: 0,
            height: boxHeight,
            minHeight: minBoxHeight,
            position: "relative",
            overflow: "auto",
            background: "rgba(10,15,30,0.4)",
            borderRadius: 10,
            border: `1px solid ${palette.borderSoft}`,
          }}
        >
          <div style={{ position: "relative", width: cw, height: ch }}>
            <div
              key={laySig}
              className="pagn-layer"
              style={{
                position: "absolute",
                left: layerL,
                top: layerT,
                transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})`,
                transformOrigin: "0 0",
                width: model.W,
                height: model.H,
              }}
            >
              {/* LAYER 2 — edges + arrow markers (painted below labels/nodes) */}
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
                  const isSel = selectedEdge?.key === le.key;
                  return (
                    <path
                      key={le.key}
                      className="pagn-edge"
                      d={d}
                      fill="none"
                      stroke={isPredicted ? palette.accent : palette.textMuted}
                      strokeWidth={isSel ? w + 2 : w}
                      strokeOpacity={isSel ? 0.95 : 0.45}
                      markerEnd={`url(#pagn-arrow-${uid})`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedEdge(le);
                        setSelectedNode(null);
                      }}
                    />
                  );
                })}
              </svg>

              {/* LAYER 3 — edge labels (compact pills, always avoided away from nodes) */}
              {model.edges.map((le) => {
                const geo = bezier(le);
                const label = `${Math.round(toPct(le.edge.weight))}%`;
                const estW = clamp(34 + label.length * 7, 64, 130);
                const pos = pickLabelPos(geo.mid, estW, 22, rects);
                const isSel = selectedEdge?.key === le.key;
                return (
                  <div
                    key={`${le.key}-label`}
                    className={isSel ? "pagn-edge-label pagn-sel" : "pagn-edge-label"}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedEdge(le);
                      setSelectedNode(null);
                    }}
                    title={`${le.source.label} → ${le.target.label} · ${le.edge.label ?? "transition"} · confidence ${pctStr(le.edge.weight)}`}
                    style={{
                      position: "absolute",
                      left: pos.x,
                      top: pos.y,
                      transform: "translate(-50%,-50%)",
                      background: "rgba(13,20,37,0.97)",
                      border: `1px solid ${isSel ? palette.accent : palette.border}`,
                      borderRadius: 999,
                      padding: "2px 9px",
                      fontSize: 10.5,
                      fontWeight: 650,
                      color: isSel ? palette.accent : palette.textDim,
                      whiteSpace: "nowrap",
                      pointerEvents: "auto",
                      cursor: "pointer",
                      zIndex: 1,
                    }}
                  >
                    {label}
                  </div>
                );
              })}

              {/* LAYERS 4–6 — node cards (opaque, sit above edges and labels) */}
              {model.nodes.map((p) => {
                const color = p.type === "current" ? palette.accent : stageColor(p.stage);
                const stepLabel = Math.round(num(p.step, 0));
                const riskPct = toPct(p.risk);
                const confPct = toPct(num(p.confidence, p.probability));
                const evidenceCount = Array.isArray(p.evidence) ? p.evidence.filter(Boolean).length : 0;
                const isSel = selectedNode?.id === p.id;
                return (
                  <div
                    key={p.id}
                    className={isSel ? "pagn-card pagn-sel" : "pagn-card"}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedNode(p);
                      setSelectedEdge(null);
                    }}
                    title={`${p.label}\nRisk ${pctStr(p.risk)} · Confidence ${pctStr(num(p.confidence, p.probability))}`}
                    style={{
                      position: "absolute",
                      left: p.x - CARD_W / 2,
                      top: p.y - CARD_H / 2,
                      width: CARD_W,
                      height: CARD_H,
                      boxSizing: "border-box",
                      display: "flex",
                      flexDirection: "column",
                      background: "rgba(10,15,30,0.95)",
                      border: `1px solid ${color}66`,
                      borderLeft: `3px solid ${color}`,
                      borderRadius: 10,
                      padding: "10px 12px",
                      cursor: "pointer",
                      zIndex: isSel ? 4 : 2,
                      boxShadow: isSel
                        ? `0 0 0 1px ${color}66, 0 14px 34px rgba(0,0,0,0.55)`
                        : "0 6px 18px rgba(0,0,0,0.35)",
                    }}
                  >
                    {/* Step badge */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: 0.6,
                          color,
                          background: `${color}1f`,
                          border: `1px solid ${color}44`,
                          borderRadius: 5,
                          padding: "1px 7px",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {p.type === "current" || stepLabel === 0 ? "NOW" : `t+${stepLabel}`}
                      </span>
                      <span style={{ marginLeft: "auto", fontSize: 10, color: palette.textMuted }}>
                        {evidenceCount > 0 ? `${evidenceCount} ev` : ""}
                      </span>
                    </div>

                    {/* Stage name — wraps instead of clipping */}
                    <div
                      style={{
                        marginTop: 7,
                        fontSize: 13.5,
                        fontWeight: 700,
                        lineHeight: 1.25,
                        color: "#dbe4ff",
                        overflowWrap: "anywhere",
                        whiteSpace: "normal",
                        wordBreak: "normal",
                      }}
                    >
                      {p.label}
                    </div>

                    {/* Risk row */}
                    <div style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: 7 }}>
                      <span style={{ fontSize: 10, color: palette.textMuted, width: 26 }}>Risk</span>
                      <div style={{ flex: 1, height: 5, borderRadius: 99, background: palette.border, overflow: "hidden" }}>
                        <div
                          style={{
                            height: "100%",
                            width: `${riskPct}%`,
                            borderRadius: 99,
                            background: riskPct >= 75 ? palette.danger : riskPct >= 50 ? palette.warn : palette.good,
                          }}
                        />
                      </div>
                      <span className="mono" style={{ fontSize: 10, color: palette.textDim, width: 32, textAlign: "right" }}>
                        {Math.round(riskPct)}%
                      </span>
                    </div>

                    {/* Footer */}
                    <div style={{ marginTop: 5, display: "flex", justifyContent: "space-between", fontSize: 10, color: palette.textMuted }}>
                      <span>Conf {Math.round(confPct)}%</span>
                      <span>Sev {num(p.severity, 0).toFixed(1)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div
            className="mono"
            style={{
              position: "sticky",
              left: 8,
              bottom: 8,
              width: "max-content",
              fontSize: 10,
              color: palette.textMuted,
              background: "rgba(13,20,37,0.78)",
              border: `1px solid ${palette.borderSoft}`,
              borderRadius: 6,
              padding: "2px 8px",
              pointerEvents: "none",
            }}
          >
            scroll to pan · wheel to zoom · {Math.round(view.s * 100)}%
          </div>
        </div>

        {model.nodes.length === 1 && model.nodes[0].type === "current" && model.forecastSteps === 0 && !selectedNode ? (
          <div style={{ flex: "0 1 240px", minWidth: 220, padding: 12, borderRadius: 10, border: `1px solid ${palette.borderSoft}`, fontSize: 11.5, color: palette.textDim, lineHeight: 1.6 }}>
            No K-step forecast produced yet. The graph will populate once the world model rollout completes.
          </div>
        ) : selectedNode && !selectedEdge ? (
          <NodeDetailPanel node={selectedNode} />
        ) : selectedEdge ? (
          <EdgeDetailPanel edge={selectedEdge} />
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

function EdgeDetailPanel({ edge }: { edge: LayoutEdge }) {
  const isPredicted = edge.edge.transition || String(edge.edge.label).includes("predicted");
  const color = isPredicted ? palette.accent : palette.textMuted;
  return (
    <div
      style={{
        flex: "0 1 240px", minWidth: 220, padding: 14, borderRadius: 10,
        border: `1px solid ${color}55`, background: "rgba(10,15,30,0.6)",
      }}
    >
      <div style={{ fontSize: 12.5, fontWeight: 700, color, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8 }}>
        Transition
      </div>
      <DetailRow label="From" value={edge.source.label} />
      <DetailRow label="To" value={edge.target.label} />
      <DetailRow label="Type" value={String(edge.edge.label ?? "transition")} />
      <DetailRow label="Confidence" value={pctStr(edge.edge.weight)} />
      {edge.target.step !== undefined && (
        <DetailRow label="Forecast step" value={edge.target.step === 0 ? "current state" : `t+${edge.target.step}`} />
      )}
      <div style={{ marginTop: 10, fontSize: 11, color: palette.textMuted, lineHeight: 1.55 }}>
        {isPredicted
          ? "The world-model rollout predicts this stage transition based on the current network state."
          : "Observed stage transition from the analyzed traffic windows."}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "3px 0", fontSize: 11.5 }}>
      <span style={{ color: palette.textDim }}>{label}</span>
      <span className="mono" style={{ color: palette.text, fontWeight: 600, textAlign: "right" }}>{value}</span>
    </div>
  );
}