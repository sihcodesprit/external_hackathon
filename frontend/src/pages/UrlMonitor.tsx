import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { palette, threatGaugeColor, stageColor } from "../styles/theme";
import { api } from "../services/api";
import { Card, Grid, Dot, Pill, Bar } from "../components/ui/primitives";
import { MetricCard } from "../components/ui/displays";
import { Button } from "../components/ui/Button";
import type {
  LiveHealthInfo,
  LiveInterface,
  LiveStatusResponse,
  UrlStatusResponse,
  UrlTimelineEvent,
} from "../types";

type Phase = "idle" | "checking" | "capturing" | "error";

interface Sample {
  t: number;
  pps: number;
  bps: number;
  up: number;
  down: number;
}

const RANGES: Array<{ label: string; seconds: number }> = [
  { label: "30s", seconds: 30 },
  { label: "60s", seconds: 60 },
  { label: "5m", seconds: 300 },
];

function fmtNum(n: number | undefined): string {
  const v = Number(n ?? 0);
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return `${v}`;
}

function fmtBytes(n: number | undefined): string {
  const v = Number(n ?? 0);
  if (v >= 1024 ** 3) return `${(v / 1024 ** 3).toFixed(2)} GB`;
  if (v >= 1024 ** 2) return `${(v / 1024 ** 2).toFixed(2)} MB`;
  if (v >= 1024) return `${(v / 1024).toFixed(1)} KB`;
  return `${v} B`;
}

function fmtRate(n: number | undefined): string {
  return `${fmtBytes(n)}/s`;
}

const timelineColor = (type: string): string => {
  switch (type) {
    case "dns":
      return palette.accent2;
    case "connection":
    case "traffic":
      return palette.good;
    case "flow":
      return palette.accent;
    case "risk":
      return palette.warn;
    case "forecast":
      return palette.danger;
    default:
      return palette.textDim;
  }
};

export default function UrlMonitor() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [health, setHealth] = useState<LiveHealthInfo | null>(null);
  const [interfaces, setInterfaces] = useState<LiveInterface[]>([]);
  const [selected, setSelected] = useState("");
  const [url, setUrl] = useState("https://example.com");
  const [status, setStatus] = useState<UrlStatusResponse | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState(30);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [timeline, setTimeline] = useState<UrlTimelineEvent[]>([]);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const applyStatus = useCallback((st: UrlStatusResponse) => {
    setStatus(st);
    if (Array.isArray(st.timeline)) setTimeline(st.timeline);
    const traffic = st.traffic;
    if (traffic) {
      setSamples((prev) => {
        const next = [
          ...prev,
          {
            t: Date.now(),
            pps: traffic.packets_per_second ?? 0,
            bps: traffic.bytes_per_second ?? 0,
            up: traffic.upload_rate ?? 0,
            down: traffic.download_rate ?? 0,
          },
        ];
        return next.length > 4000 ? next.slice(next.length - 4000) : next;
      });
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [h, ifaces, live] = await Promise.all([
          api.liveHealth(),
          api.liveInterfaces(),
          api.liveStatus(),
        ]);
        if (!mounted) return;
        setHealth(h);
        setInterfaces(ifaces);
        if (!selected) {
          const up = ifaces.filter((i) => i.is_up && i.name !== "lo");
          setSelected(up[0]?.name ?? ifaces[0]?.name ?? "");
        }
        const st = live as LiveStatusResponse;
        if (st.active && st.mode === "live_url" && st.analysis_id) {
          setAnalysisId(st.analysis_id);
          setPhase("capturing");
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

  // Poll the full URL status (risk / forecast / graph) while capturing.
  useEffect(() => {
    if (phase !== "capturing" || !analysisId) return;
    const tick = async () => {
      try {
        const st = await api.liveUrlStatus(analysisId);
        applyStatus(st);
      } catch {
        /* transient — SSE/poll will retry */
      }
    };
    tick();
    pollRef.current = setInterval(tick, 2500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [phase, analysisId, applyStatus]);

  // SSE for real-time channels published by the backend.
  useEffect(() => {
    if (phase !== "capturing") return;
    const es = new EventSource(api.liveEventsUrl());
    esRef.current = es;

    const mergeTimeline = (ev: UrlTimelineEvent) => {
      if (!ev || !ev.type) return;
      setTimeline((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.timestamp === ev.timestamp && last.type === ev.type && last.message === ev.message) {
          return prev;
        }
        const next = [...prev, ev];
        return next.length > 300 ? next.slice(next.length - 300) : next;
      });
    };

    const onUpdate = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as Record<string, unknown>;
        if (Array.isArray((data as { timeline?: unknown }).timeline)) {
          setTimeline((data as { timeline: UrlTimelineEvent[] }).timeline);
        }
      } catch {
        /* ignore */
      }
    };

    const names = [
      "url_status", "dns", "connection", "traffic", "flow",
      "network_state", "risk", "forecast", "stage", "graph",
      "mitre", "explainability", "counterfactual",
    ];
    const onNamed = (name: string) => (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as Record<string, unknown>;
        if (["dns", "connection", "traffic", "flow", "risk", "forecast"].includes(name)) {
          mergeTimeline({
            timestamp: String(data.timestamp ?? new Date().toISOString()),
            type: name === "risk" ? "risk" : name === "forecast" ? "forecast" : name,
            message: String(data.message ?? name),
            data,
          });
        }
        if (name === "url_status") {
          setStatus((prev) => (prev ? { ...prev, traffic: (data.traffic as UrlStatusResponse["traffic"]) ?? prev.traffic, url_metrics: data.url_metrics as Record<string, unknown> } : prev));
          const traffic = data.traffic as UrlStatusResponse["traffic"] | undefined;
          if (traffic) {
            setSamples((prev) => {
              const next = [...prev, {
                t: Date.now(),
                pps: traffic.packets_per_second ?? 0,
                bps: traffic.bytes_per_second ?? 0,
                up: traffic.upload_rate ?? 0,
                down: traffic.download_rate ?? 0,
              }];
              return next.length > 4000 ? next.slice(next.length - 4000) : next;
            });
          }
        }
      } catch {
        /* ignore */
      }
    };

    es.addEventListener("update", onUpdate);
    names.forEach((n) => es.addEventListener(n, onNamed(n) as EventListener));
    es.addEventListener("stopped", () => {
      setPhase("idle");
      setStatus(null);
      es.close();
    });
    es.onerror = () => {
      /* polling keeps the dashboard fresh if SSE drops */
    };
    return () => {
      es.close();
      esRef.current = null;
    };
  }, [phase]);

  const start = async () => {
    if (!selected || !url.trim()) return;
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
      const res = await api.liveUrlStart({ url: url.trim(), interface: selected });
      if (res.error) {
        setError(res.error);
        setPhase("error");
        return;
      }
      setSamples([]);
      setTimeline([]);
      setAnalysisId(res.analysis_id);
      setPhase("capturing");
    } catch (e) {
      setError((e as Error).message);
      setPhase("error");
    }
  };

  const stop = async () => {
    try {
      await api.liveUrlStop(analysisId ?? undefined);
    } catch {
      /* ignore */
    } finally {
      setPhase("idle");
      setStatus(null);
    }
  };

  const target = status?.target ?? null;
  const traffic = status?.traffic;
  const risk = status?.risk ?? {};
  const future = status?.forecast?.future ?? [];
  const currentRisk = Number(risk.current_risk ?? 0);
  const futureRisk = Number(risk.future_max_risk ?? 0);
  const hasTraffic = (traffic?.packets ?? 0) > 0;
  const hasModel = status?.world_model_status === "ready";

  const visible = useMemo(() => {
    const cutoff = Date.now() - range * 1000;
    return samples.filter((s) => s.t >= cutoff);
  }, [samples, range]);

  const maxPps = Math.max(1, ...visible.map((s) => s.pps));
  const maxBps = Math.max(1, ...visible.map((s) => s.bps));

  const futureStages = future.slice(0, 5);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, letterSpacing: 0.2 }}>
            URL Transmission Monitor
          </h1>
          <p style={{ fontSize: 12.5, color: palette.textMuted, marginTop: 4 }}>
            Resolves a URL to its destination infrastructure and observes real local network
            transmission with TShark. This is a network monitor — not a website content scraper.
          </p>
        </div>
        {phase === "capturing" ? (
          <Button variant="danger" size="sm" onClick={stop}>STOP</Button>
        ) : (
          <Button
            size="sm"
            onClick={start}
            disabled={!selected || !url.trim() || phase === "checking" || !health?.available}
            title={!health?.available ? "TShark is required for real-time URL traffic monitoring" : undefined}
          >
            {phase === "checking"
              ? "Starting…"
              : !health?.available
              ? "Install TShark to enable"
              : "START URL MONITOR"}
          </Button>
        )}
      </div>

      {/* Configuration */}
      <Card title="URL MONITOR" subtitle="Enter a URL, validate it, resolve DNS, and monitor observed traffic">
        <Grid cols="2fr 1fr 1fr" gap={14}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={labelStyle}>Enter URL</span>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={phase === "capturing"}
              placeholder="https://example.com"
              className="mono"
              style={inputStyle}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={labelStyle}>Interface</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={phase === "capturing"}
              style={inputStyle}
            >
              {interfaces.length === 0 && <option value="">No interfaces detected</option>}
              {interfaces.map((i) => (
                <option key={i.name} value={i.name}>
                  {i.name} — {i.addresses[0] ?? "no addresses"}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={labelStyle}>Mode</span>
            <select value="URL MONITOR" disabled style={inputStyle}>
              <option>URL MONITOR</option>
            </select>
          </div>
        </Grid>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
          <Dot color={phase === "capturing" ? palette.good : health?.available ? palette.textMuted : palette.danger} />
          <span style={{ fontSize: 12, color: palette.textDim }}>
            {phase === "capturing"
              ? "TSHARK ACTIVE"
              : health?.available
                ? `TShark v${health.version ?? "?"} ready`
                : "TShark not available"}
          </span>
          {status?.status && <Pill tone={phase === "capturing" ? "good" : "default"}>{status.status}</Pill>}
        </div>
        {error && (
          <div style={{ marginTop: 12, padding: "8px 12px", borderRadius: 8, background: `${palette.danger}14`, border: `1px solid ${palette.danger}40`, color: palette.danger, fontSize: 12 }}>
            {error}
          </div>
        )}
      </Card>

      {phase === "capturing" && (
        <>
          <div style={{ height: 16 }} />
          {/* Target + scope */}
          <Grid cols="1fr 1.6fr" gap={14}>
            <Card title="Target" subtitle="Resolved destination infrastructure">
              <Row k="URL" v={target?.url ?? url} mono />
              <Row k="Hostname" v={target?.hostname ?? "—"} mono />
              <Row k="Scheme" v={target?.scheme ?? "—"} />
              <Row k="Port" v={String(target?.port ?? "—")} mono />
              <Row k="Resolved IPs" v={String(target?.resolved_ips?.length ?? 0)} />
              <Row k="Interface" v={status?.interface ?? selected} mono />
              <Row k="Capture" v={phase === "capturing" ? "● RUNNING" : "stopped"} />
              <Row k="TShark" v={phase === "capturing" ? "● RUNNING" : "stopped"} />
            </Card>

            <Card title="Monitoring source & scope" subtitle="What this monitor can and cannot see">
              <div style={{ fontSize: 12, color: palette.textDim, lineHeight: 1.7 }}>
                <div><strong style={{ color: palette.text }}>MONITORING SOURCE:</strong> Linux interface <span className="mono">{status?.interface ?? selected}</span></div>
                <div><strong style={{ color: palette.text }}>TARGET:</strong> <span className="mono">{target?.hostname ?? "—"}</span></div>
                <div style={{ marginTop: 8 }}>
                  This system monitors traffic observable on the selected interface. It does not
                  remotely inspect the target server, does not bypass TLS encryption, and does not
                  claim visibility into traffic outside the local capture point.
                </div>
                {target?.scheme === "HTTPS" && (
                  <div style={{ marginTop: 10, padding: "8px 10px", borderRadius: 8, background: palette.accentSoft, border: `1px solid ${palette.accentBorder}`, color: palette.accent }}>
                    HTTPS traffic is encrypted. This monitor analyzes observable network metadata
                    and traffic behavior; application payload contents are not inspected.
                  </div>
                )}
                {(target?.resolution_count ?? 0) > 1 && (
                  <div style={{ marginTop: 10, color: palette.warn }}>
                    TARGET IPs UPDATED · previous {target?.previous_ips?.length ?? 0} IPs →
                    current {target?.resolved_ips?.length ?? 0} IPs
                  </div>
                )}
              </div>
            </Card>
          </Grid>

          <div style={{ height: 16 }} />

          {/* Real-time transmission */}
          <Grid cols="repeat(4, 1fr)" gap={12}>
            <MetricCard label="Upload rate" value={fmtRate(traffic?.upload_rate)} sub={`${fmtNum(traffic?.outbound_bytes)} outbound`} tone="accent" />
            <MetricCard label="Download rate" value={fmtRate(traffic?.download_rate)} sub={`${fmtNum(traffic?.inbound_bytes)} inbound`} tone="good" />
            <MetricCard label="Packets" value={fmtNum(traffic?.packets)} sub={`${(traffic?.packets_per_second ?? 0).toFixed(1)} pkt/s`} />
            <MetricCard label="Bytes" value={fmtBytes(traffic?.bytes)} sub={fmtRate(traffic?.bytes_per_second)} />
            <MetricCard label="Active flows" value={fmtNum(traffic?.flows)} sub="target conversations" />
            <MetricCard label="TCP connections" value={fmtNum(traffic?.syn_count)} sub={`${fmtNum(traffic?.tls_connections)} TLS handshakes`} />
            <MetricCard label="RST / Retrans" value={`${fmtNum(traffic?.rst_count)} / ${fmtNum(traffic?.retransmissions)}`} sub="reset / retransmission" tone="danger" />
            <MetricCard label="Network states" value={fmtNum(status?.network_state ? 1 : 0)} sub={hasModel ? "world model ready" : "warming up"} tone="accent" />
          </Grid>

          {!hasTraffic && (
            <div style={{ marginTop: 14, padding: "12px 16px", borderRadius: 10, background: palette.bgElevated, border: `1px solid ${palette.border}`, color: palette.textDim, fontSize: 12.5 }}>
              ● MONITORING — Target: <span className="mono">{target?.hostname}</span>. Monitoring active.
              No matching traffic observed yet.
            </div>
          )}

          <div style={{ height: 16 }} />

          {/* Live graph */}
          <Card
            title="Real-time transmission"
            subtitle="Observed packets/sec and bytes/sec for the target"
            headerRight={
              <div style={{ display: "flex", gap: 6 }}>
                {RANGES.map((r) => (
                  <button
                    key={r.seconds}
                    onClick={() => setRange(r.seconds)}
                    style={{
                      ...rangeBtnStyle,
                      background: range === r.seconds ? palette.accentSoft : "transparent",
                      color: range === r.seconds ? palette.accent : palette.textDim,
                      borderColor: range === r.seconds ? palette.accentBorder : palette.border,
                    }}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            }
          >
            <RateChart samples={visible} maxPps={maxPps} maxBps={maxBps} />
            <div style={{ display: "flex", gap: 18, marginTop: 8, fontSize: 11, color: palette.textDim }}>
              <Legend color={palette.accent} label="Packets/sec" />
              <Legend color={palette.accent2} label="Bytes/sec" />
            </div>
          </Card>

          <div style={{ height: 16 }} />

          {/* Behavior + risk */}
          <Grid cols="1.3fr 1fr" gap={14}>
            <Card title="Network behavior" subtitle="Derived from real observed target traffic">
              <BehaviorRows status={status} />
            </Card>

            <Card title="AI forecast" subtitle="Existing Cyber World Model — no URL-specific rules">
              {hasModel && (currentRisk > 0 || future.length > 0) ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <Grid cols="1fr 1fr" gap={12}>
                    <div>
                      <span style={labelStyle}>Current risk</span>
                      <div className="mono" style={{ fontSize: 30, fontWeight: 700, color: gauge(currentRisk) }}>
                        {(currentRisk * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div>
                      <span style={labelStyle}>Future max risk</span>
                      <div className="mono" style={{ fontSize: 30, fontWeight: 700, color: gauge(futureRisk) }}>
                        {(futureRisk * 100).toFixed(0)}%
                      </div>
                    </div>
                  </Grid>
                  <Bar value={currentRisk * 100} color={gauge(currentRisk)} height={10} />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: palette.textDim }}>
                    <span>Trend: <strong style={{ color: palette.text }}>{String(risk.risk_trend ?? "stable")}</strong></span>
                    <span>Model confidence: <strong style={{ color: palette.text }}>{(Number(risk.confidence ?? 0)).toFixed(2)}</strong></span>
                  </div>
                  <div>
                    <span style={labelStyle}>Predicted future state</span>
                    <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.max(futureStages.length, 1)}, 1fr)`, gap: 8, marginTop: 6 }}>
                      {futureStages.map((f, i) => (
                        <div key={i} style={{ padding: "8px 6px", borderRadius: 8, background: palette.bgElevated, border: `1px solid ${palette.borderSoft}`, textAlign: "center" }}>
                          <div style={{ fontSize: 10.5, color: palette.textMuted }}>t+{f.step ?? i + 1}</div>
                          <div className="mono" style={{ fontSize: 14, color: gauge(f.risk ?? 0) }}>{((f.risk ?? 0) * 100).toFixed(0)}%</div>
                          <div style={{ fontSize: 10, color: stageColor(f.stage ?? "Unknown") }}>{f.stage ?? "—"}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: 12.5, color: palette.textDim }}>
                  RISK: INSUFFICIENT DATA
                  <div style={{ marginTop: 6, color: palette.textMuted }}>
                    The world model needs more observed windows before producing a valid prediction.
                  </div>
                </div>
              )}
            </Card>
          </Grid>

          <div style={{ height: 16 }} />

          {/* Timeline */}
          <Card title="Live transmission events" subtitle="Every entry originates from the real TShark pipeline">
            {timeline.length === 0 ? (
              <span style={{ fontSize: 12, color: palette.textMuted }}>No events observed yet.</span>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", maxHeight: 280, overflowY: "auto", gap: 5 }}>
                {[...timeline].slice(-80).reverse().map((ev, i) => (
                  <div key={`${ev.timestamp}-${i}`} style={{ display: "flex", gap: 10, alignItems: "baseline", fontSize: 11.5 }}>
                    <Dot color={timelineColor(ev.type)} size={6} />
                    <span className="mono" style={{ color: palette.textMuted, flexShrink: 0 }}>
                      {ev.timestamp.split("T")[1]?.slice(0, 8) ?? ev.timestamp}
                    </span>
                    <span style={{ color: timelineColor(ev.type), minWidth: 84 }}>{ev.type}</span>
                    <span style={{ color: palette.textDim }}>{ev.message}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {target?.resolved_ips && target.resolved_ips.length > 0 && (
            <>
              <div style={{ height: 16 }} />
              <Card title="Resolved destination set" subtitle={`${target.resolved_ips.length} address(es) — continuously refreshed`}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {target.resolved_ips.map((ip) => (
                    <span key={ip} className="mono" style={{ padding: "3px 10px", borderRadius: 999, background: palette.bgElevated, border: `1px solid ${palette.border}`, fontSize: 11.5, color: palette.text }}>
                      {ip}
                    </span>
                  ))}
                </div>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}

function BehaviorRows({ status }: { status: UrlStatusResponse | null }) {
  const t = status?.traffic;
  const m = (status?.url_metrics ?? {}) as Record<string, number>;
  const rows: Array<[string, string]> = [
    ["Packet rate", `${(t?.packets_per_second ?? 0).toFixed(1)} /s`],
    ["Byte rate", fmtRate(t?.bytes_per_second)],
    ["IAT mean / variance", `${(m.iat_mean ?? 0).toFixed(4)}s / ${(m.iat_variance ?? 0).toExponential(2)}`],
    ["Avg packet size / variance", `${(m.average_packet_size ?? 0).toFixed(1)} B / ${(m.packet_size_variance ?? 0).toFixed(1)}`],
    ["TCP handshake SYN/SYN-ACK", `${t?.syn_count ?? 0} / ${Math.max(0, (t?.syn_count ?? 0) - (t?.rst_count ?? 0))}`],
    ["RST count", String(t?.rst_count ?? 0)],
    ["Retransmissions", String(t?.retransmissions ?? 0)],
    ["TLS handshakes", String(t?.tls_connections ?? 0)],
    ["Destination IPs observed", `${t?.active_connections ?? 0} flow-connections`],
    ["DNS resolutions", String(t?.resolutions ?? 0)],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {rows.map(([k, v]) => (
        <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "5px 0", borderBottom: `1px solid ${palette.borderSoft}` }}>
          <span style={{ fontSize: 11.5, color: palette.textDim }}>{k}</span>
          <span className="mono" style={{ fontSize: 12, color: palette.text }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

function RateChart({ samples, maxPps, maxBps }: { samples: Sample[]; maxPps: number; maxBps: number }) {
  const W = 600;
  const H = 150;
  const pad = 8;
  const n = samples.length;
  const now = Date.now();
  const span = 30000;
  const x = (t: number) => pad + (1 - (now - t) / span) * (W - pad * 2);
  const line = (key: "pps" | "bps", max: number) => {
    if (n === 0) return "";
    return samples
      .map((s, i) => {
        const px = x(s.t);
        const py = H - pad - Math.min(1, s[key] / max) * (H - pad * 2);
        return `${i === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`;
      })
      .join(" ");
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: 160, display: "block" }}>
      {[0.25, 0.5, 0.75].map((f) => (
        <line key={f} x1={pad} x2={W - pad} y1={pad + f * (H - pad * 2)} y2={pad + f * (H - pad * 2)} stroke={palette.chartGrid} strokeWidth={1} />
      ))}
      {n > 1 && <path d={line("bps", maxBps)} fill="none" stroke={palette.accent2} strokeWidth={1.6} opacity={0.85} />}
      {n > 1 && <path d={line("pps", maxPps)} fill="none" stroke={palette.accent} strokeWidth={1.8} />}
      {n === 0 && (
        <text x={W / 2} y={H / 2} textAnchor="middle" fill={palette.textMuted} fontSize={12}>
          Waiting for observed traffic…
        </text>
      )}
    </svg>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 14, height: 2, background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}

function gauge(risk: number): string {
  const pct = risk * 100;
  if (pct >= 75) return threatGaugeColor("CRITICAL");
  if (pct >= 55) return threatGaugeColor("HIGH");
  if (pct >= 30) return threatGaugeColor("MEDIUM");
  return threatGaugeColor("LOW");
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "4px 0", borderBottom: `1px solid ${palette.borderSoft}` }}>
      <span style={{ fontSize: 11.5, color: palette.textDim }}>{k}</span>
      <span className={mono ? "mono" : ""} style={{ fontSize: 12, color: palette.text, textAlign: "right", overflow: "hidden", textOverflow: "ellipsis" }}>{v}</span>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: palette.textDim,
  textTransform: "uppercase",
  letterSpacing: 0.8,
};

const inputStyle: React.CSSProperties = {
  appearance: "none",
  background: palette.bgElevated,
  color: palette.text,
  border: `1px solid ${palette.border}`,
  borderRadius: 8,
  padding: "7px 10px",
  fontSize: 12.5,
  width: "100%",
  boxSizing: "border-box",
};

const rangeBtnStyle: React.CSSProperties = {
  appearance: "none",
  border: "1px solid",
  borderRadius: 6,
  padding: "3px 9px",
  fontSize: 11,
  cursor: "pointer",
};