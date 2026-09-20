import { useCallback, useEffect, useRef, useState } from "react";
import { palette, stageColor, threatGaugeColor } from "../styles/theme";
import { api } from "../services/api";
import { Card, Grid, Dot, Pill, Bar } from "../components/ui/primitives";
import { MetricCard } from "../components/ui/displays";
import { Button } from "../components/ui/Button";
import type {
  LiveHealthInfo,
  LiveInterface,
  LiveSessionHistory,
  LiveStatusResponse,
} from "../types";

type Phase = "idle" | "checking" | "capturing" | "error";

const statusTone = (s: string): "default" | "accent" | "good" | "warn" | "danger" => {
  switch (s) {
    case "capturing":
    case "ready":
      return "good";
    case "analyzing":
    case "warming_up":
    case "starting":
      return "accent";
    case "error":
      return "danger";
    default:
      return "default";
  }
};

export default function LiveMonitor({ bare = false }: { bare?: boolean } = {}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [health, setHealth] = useState<LiveHealthInfo | null>(null);
  const [interfaces, setInterfaces] = useState<LiveInterface[]>([]);
  const [selected, setSelected] = useState("");
  const [status, setStatus] = useState<LiveStatusResponse | null>(null);
  const [history, setHistory] = useState<LiveSessionHistory[]>([]);
  const [events, setEvents] = useState<Array<{ type: string; data: Record<string, unknown> }>>([]);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const refreshAll = useCallback(async () => {
    try {
      const st = await api.liveStatus();
      setStatus(st);
      if (st.active && st.analysis_id) {
        setAnalysisId(st.analysis_id ?? analysisId);
        setPhase("capturing");
      } else {
        setPhase((p) => (p === "capturing" ? "idle" : p));
      }
    } catch {
      /* backend not ready */
    }
  }, [analysisId]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [h, ifaces] = await Promise.all([api.liveHealth(), api.liveInterfaces()]);
        if (!mounted) return;
        setHealth(h);
        setInterfaces(ifaces);
        if (!selected) {
          const up = ifaces.filter((i) => i.is_up);
          setSelected(up[0]?.name ?? ifaces[0]?.name ?? "");
        }
      } catch (e) {
        if (mounted) setError((e as Error).message);
      }
    })();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api.liveHistory().then(setHistory).catch(() => {});
  }, [refreshKey]);

  // Poll status while not streaming via SSE
  useEffect(() => {
    if (phase === "capturing") return;
    pollRef.current = setInterval(() => {
      refreshAll();
    }, 4000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [phase, refreshAll]);

  // Connect SSE when capturing
  useEffect(() => {
    if (phase !== "capturing") return;
    const es = new EventSource(api.liveEventsUrl());
    esRef.current = es;
    es.onmessage = (ev) => {
      try {
        setStatus(JSON.parse(ev.data) as LiveStatusResponse);
      } catch {
        /* ignore malformed */
      }
    };
    es.addEventListener("update", (ev) => {
      try {
        setStatus(JSON.parse((ev as MessageEvent).data) as LiveStatusResponse);
      } catch {
        /* ignore */
      }
    });
    es.addEventListener("stopped", () => {
      setPhase("idle");
      setStatus(null);
      es.close();
    });
    es.onerror = () => {
      /* transient SSE errors are ignored; polling takes over */
    };
    return () => {
      es.close();
      esRef.current = null;
    };
  }, [phase]);

  const start = async () => {
    if (!selected) return;
    setError(null);
    // Ensure TShark is available first
    const h = health ?? (await api.liveHealth());
    setHealth(h);
    if (!h?.available) {
      setError("TShark is not available. Install Wireshark (tshark) or set TSHARK_PATH.");
      setPhase("error");
      return;
    }
    setPhase("checking");
    try {
      const res = await api.liveStart({ interface: selected });
      if (res.error) {
        setError(res.error);
        setPhase("error");
        return;
      }
      setAnalysisId(res.analysis_id);
      setPhase("capturing");
    } catch (e) {
      setError((e as Error).message);
      setPhase("error");
    }
  };

  const stop = async () => {
    try {
      await api.liveStop();
    } finally {
      setPhase("idle");
      setStatus(null);
      setTimeout(() => setRefreshKey((k) => k + 1), 800);
    }
  };

  const cleanPhase = (s?: string) => (s ?? "stopped").replace("_", " ");

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        {!bare && (
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, letterSpacing: 0.2 }}>
              Live TShark Monitor
            </h1>
            <p style={{ fontSize: 12.5, color: palette.textMuted, marginTop: 4 }}>
              Real-time packet capture via TShark (Threadripper JSON) with live world-model forecasting.
            </p>
          </div>
        )}
        {phase === "capturing" ? (
          <Button variant="danger" size="sm" onClick={stop}>
            Stop capture
          </Button>
        ) : (
          <Button
            size="sm"
            onClick={start}
            disabled={!selected || phase === "checking" || !health?.available}
            title={!health?.available ? "Install TShark to enable live network monitoring" : undefined}
          >
            {phase === "checking"
              ? "Starting…"
              : !health?.available
              ? "Install TShark to enable"
              : "Start capture"}
          </Button>
        )}
      </div>

      {/* Health + interface selection */}
      <Card title="Capture configuration" subtitle="TShark is the only packet capture source">
        <Grid cols="1fr 1fr 1fr" gap={14}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 11, color: palette.textDim, textTransform: "uppercase", letterSpacing: 0.8 }}>TShark status</span>
            {health ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Dot color={health.available ? palette.good : palette.danger} />
                <span style={{ fontSize: 12.5, color: health.available ? palette.text : palette.danger }}>
                  {health.available ? `v${health.version ?? "?"}` : "Not available"}
                </span>
                {health.path && <span className="mono" style={{ fontSize: 10.5, color: palette.textMuted }}>{health.path}</span>}
              </div>
            ) : (
              <span style={{ fontSize: 12.5, color: palette.textMuted }}>Checking…</span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 11, color: palette.textDim, textTransform: "uppercase", letterSpacing: 0.8 }}>Interface</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={phase === "capturing"}
              style={{
                appearance: "none",
                background: palette.bgElevated,
                color: palette.text,
                border: `1px solid ${palette.border}`,
                borderRadius: 8,
                padding: "7px 10px",
                fontSize: 12.5,
                width: "100%",
              }}
            >
              {interfaces.length === 0 && <option value="">No interfaces detected</option>}
              {interfaces.map((i) => (
                <option key={i.name} value={i.name}>
                  {i.name} — {i.description || (i.addresses[0] ?? "no addresses")}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 11, color: palette.textDim, textTransform: "uppercase", letterSpacing: 0.8 }}>Session status</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Pill tone={statusTone(status?.status)}>{cleanPhase(status?.status ?? "stopped")}</Pill>
              {status?.world_model_status === "ready" && <Pill tone="good">model ready</Pill>}
            </div>
          </div>
        </Grid>
        {error && (
          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              borderRadius: 8,
              background: `${palette.danger}14`,
              border: `1px solid ${palette.danger}40`,
              color: palette.danger,
              fontSize: 12,
            }}
          >
            {error}
          </div>
        )}
      </Card>

      {phase === "capturing" && (
        <>
          {/* Live metrics */}
          <div style={{ height: 16 }} />
          <Grid cols="repeat(4, 1fr)" gap={12}>
            <MetricCard
              label="Packets"
              value={String(status?.packets ?? 0)}
              sub={`${Number(status?.packets_per_second ?? 0).toFixed(1)} pkt/s`}
              tone="accent"
            />
            <MetricCard
              label="Flows"
              value={String(status?.flows ?? 0)}
              sub="active conversations"
            />
            <MetricCard
              label="Hosts"
              value={String(status?.hosts ?? 0)}
              sub="distinct endpoints"
            />
            <MetricCard
              label="Network states"
              value={String(status?.states_count ?? 0)}
              sub={`${Number(status?.bytes_per_second ?? 0).toFixed(1)} B/s`}
              tone="good"
            />
          </Grid>

          <div style={{ height: 16 }} />

          {/* Risk + window config */}
          <Grid cols="2fr 1fr" gap={14}>
            <Card title="Current threat" subtitle="Live risk from the continuously-fitted world model">
              {status ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
                    <span
                      className="mono"
                      style={{
                        fontSize: 40,
                        fontWeight: 700,
                        lineHeight: 1,
                        color: threatGaugeColor(
                          (status.current_risk ?? 0) * 100 >= 75
                            ? "CRITICAL"
                            : (status.current_risk ?? 0) * 100 >= 55
                              ? "HIGH"
                              : (status.current_risk ?? 0) * 100 >= 30
                                ? "MEDIUM"
                                : "LOW",
                        ),
                      }}
                    >
                      {((status.current_risk ?? 0) * 100).toFixed(1)}
                      <span style={{ fontSize: 14, color: palette.textMuted, marginLeft: 4 }}>risk</span>
                    </span>
                    <span style={{ fontSize: 13, color: stageColor(status.current_stage ?? "Unknown") }}>
                      {status.current_stage ?? "Unknown"}
                    </span>
                  </div>
                  <Bar value={(status.current_risk ?? 0) * 100} color={threatGaugeColor(
                    (status.current_risk ?? 0) * 100 >= 75 ? "CRITICAL" : (status.current_risk ?? 0) * 100 >= 55 ? "HIGH" : (status.current_risk ?? 0) * 100 >= 30 ? "MEDIUM" : "LOW",
                  )} height={10} />
                </div>
              ) : (
                <span style={{ fontSize: 12, color: palette.textMuted }}>Collecting initial data…</span>
              )}
            </Card>

            <Card title="Window configuration" subtitle="Live pipeline settings">
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <Row k="Window" v={`${status?.window_size ?? 30}s`} />
                <Row k="Step" v={`${status?.step_size ?? 5}s`} />
                <Row k="Forecast horizon" v={`${status?.forecast_horizon ?? 5} steps`} />
                <Row k="Interface" v={status?.interface ?? selected} mono />
                <Row k="Events processed" v={`${status?.events_processed ?? 0} / ${status?.events_received ?? 0}`} />
                <Row k="Events dropped" v={`${status?.events_dropped ?? 0}`} />
              </div>
            </Card>
          </Grid>

          <div style={{ height: 16 }} />

          {/* Event log */}
          <Card title="Live event log" subtitle="Window rollovers, model fits and analysis runs">
            <div style={{ display: "flex", flexDirection: "column", maxHeight: 260, overflowY: "auto", gap: 4 }}>
              {events.length === 0 && status?.last_event && (
                <LogRow
                  ts={String((status.last_event as { timestamp?: string }).timestamp ?? "")}
                  type={String((status.last_event as { type?: string }).type ?? "")}
                  msg={String((status.last_event as { message?: string }).message ?? "")}
                />
              )}
              {events.map((ev, i) => (
                <LogRow
                  key={i}
                  ts={String((ev.data as { timestamp?: string }).timestamp ?? "")}
                  type={String(ev.data.type ?? "")}
                  msg={String(ev.data.message ?? "")}
                />
              ))}
            </div>
          </Card>
        </>
      )}

      {/* Prior sessions */}
      {!phase ||
        (phase === "idle" && (
          <>
            <div style={{ height: 18 }} />
            <Card title="Previous live sessions" subtitle="Completed capture runs">
              {history.length === 0 ? (
                <span style={{ fontSize: 12, color: palette.textMuted }}>No prior live sessions recorded.</span>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {history.map((s) => (
                    <div
                      key={s.analysis_id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 10,
                        padding: "8px 12px",
                        borderRadius: 8,
                        background: palette.bgElevated,
                        border: `1px solid ${palette.borderSoft}`,
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                        <span className="mono" style={{ fontSize: 12, color: palette.text }}>{s.interface}</span>
                        <span style={{ fontSize: 10.5, color: palette.textMuted }}>
                          {s.started_at} → {s.stopped_at ?? "…"}
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: 14, fontSize: 11, color: palette.textDim }}>
                        <span>{s.packets} pkts</span>
                        <span>{s.flows} flows</span>
                        <span>{s.hosts} hosts</span>
                        <span>{s.states} states</span>
                        <span style={{ color: s.world_model_status === "ready" ? palette.good : palette.textMuted }}>
                          model: {s.world_model_status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        ))}

      {analysisId && phase === "capturing" && (
        <div style={{ marginTop: 12 }}>
          <Button variant="outline" size="sm" onClick={() => open("/", "_self")}>
            Open live analysis document
          </Button>
        </div>
      )}
    </div>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
      <span style={{ fontSize: 11.5, color: palette.textDim }}>{k}</span>
      <span className={mono ? "mono" : ""} style={{ fontSize: 12, color: palette.text, textAlign: "right" }}>
        {v}
      </span>
    </div>
  );
}

function LogRow({ ts, type, msg }: { ts: string; type: string; msg: string }) {
  const color = type === "error" ? palette.danger : type === "model" ? palette.accent2 : palette.textDim;
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "baseline", fontSize: 11.5 }}>
      <Dot color={color} size={6} />
      <span className="mono" style={{ color: palette.textMuted, flexShrink: 0 }}>
        {ts.split("T")[1]?.slice(0, 8) ?? ts}
      </span>
      <span style={{ color }}>
        {type}
      </span>
      <span style={{ color: palette.textDim, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {msg}
      </span>
    </div>
  );
}