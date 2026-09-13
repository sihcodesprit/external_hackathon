import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { palette, stageColor } from "../styles/theme";
import { api } from "../services/api";
import { useAnalysis } from "../store/analysisContext";
import type { ModelTestRunJob } from "../types";
import { Card, Pill } from "../components/ui/primitives";
import { ErrorState, PageLoader } from "../components/ui/displays";
import { fmtDuration } from "../utils/format";
import { VisualizationBoundary } from "../components/ui/VisualizationBoundary";
import { AttackGraphView } from "../components/charts/AttackGraphView";

const reduceMotion =
  typeof window !== "undefined" &&
  !!window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function ModelTestRun() {
  const { jobId = "" } = useParams<{ jobId: string }>();
  const adoptCompletedJob = useAnalysis().adoptCompletedJob;
  const [job, setJob] = useState<ModelTestRunJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);

  const alive = useRef(true);
  const timer = useRef<number | undefined>(undefined);
  const clock = useRef<number | undefined>(undefined);
  const startedAt = useRef<string | null>(null);
  const justFinished = useRef<boolean>(false);
  const adoptedJob = useRef<string | null>(null);

  const fetchJob = useCallback(async () => {
    try {
      const j = await api.modelTestJob(jobId);
      if (!alive.current) return;
      setJob(j);
      setNotFound(false);
      if (j.started_at) startedAt.current = j.started_at;
      const terminal = ["completed", "partial_failed", "error", "failed"].includes(j.status);
      if (terminal) {
        if (!justFinished.current) justFinished.current = true;
        if (
          (j.status === "completed" || j.status === "partial_failed") &&
          adoptedJob.current !== jobId
        ) {
          adoptedJob.current = jobId;
          // Share this run's analysis with every other screen (Overview,
          // Forecast, Attack Graph, MITRE, ...) so they stop showing
          // "No analysis loaded".
          void adoptCompletedJob(jobId);
        }
        setError(null);
        return;
      }
      timer.current = window.setTimeout(fetchJob, 900);
    } catch (e) {
      if (!alive.current) return;
      const status = (e as { status?: number }).status;
      if (status === 404) {
        setNotFound(true);
      } else {
        setError(e instanceof Error ? e.message : String(e));
        timer.current = window.setTimeout(fetchJob, 2000);
      }
    }
  }, [jobId, adoptCompletedJob]);

  useEffect(() => {
    alive.current = true;
    justFinished.current = false;
    fetchJob();
    clock.current = window.setInterval(() => {
      if (startedAt.current) {
        const ms = Date.now() - new Date(startedAt.current).getTime();
        if (Number.isFinite(ms)) setElapsed(Math.floor(ms / 1000));
      }
    }, 1000);
    return () => {
      alive.current = false;
      if (timer.current) window.clearTimeout(timer.current);
      if (clock.current) window.clearInterval(clock.current);
    };
  }, [fetchJob]);

  const retryModule = async (moduleId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await api.modelTestRetry(jobId, moduleId);
      justFinished.current = false;
      setJob((j) => (j ? { ...j, status: "running" } : j));
      timer.current && window.clearTimeout(timer.current);
      fetchJob();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (notFound) return <ErrorState message="Model test job not found. It may have been cleaned up after a server restart." />;
  if (!job && error) return <ErrorState message={error} />;
  if (!job) return <PageLoader label="Loading model test run…" />;

  const running = ["queued", "running"].includes(job.status);
  const doneCount = job.modules.filter((m) => m.status === "ok").length;
  const failedCount = job.modules.filter((m) => m.status === "failed").length;
  const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
  const totalTime =
    job.finished_at && job.started_at
      ? Math.max(0, (new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)
      : elapsed;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 6 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text }}>
          {running ? "RUNNING MODEL TESTS" : job.status === "error" ? "MODEL TEST FAILED" : "MODEL TEST COMPLETE"}
        </h1>
        <Link to="/model-test" style={{ fontSize: 12, color: palette.accent }}>← Model Test Center</Link>
      </div>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 16 }}>
        Job <span className="mono">{job.job_id}</span>
      </p>

      {error && (
        <div style={{ marginBottom: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.4)", fontSize: 12, color: palette.danger }}>
          ⚠ {error}
        </div>
      )}

      {/* Progress */}
      <Card title={running ? "Overall Progress" : "Result Summary"}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ flex: 1, height: 10, borderRadius: 999, background: palette.border, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${progress}%`,
                  borderRadius: 999,
                  background: "linear-gradient(90deg,#0ea5e9,#22d3ee)",
                  transition: reduceMotion ? "none" : "width 500ms ease",
                }}
              />
            </div>
            <span className="mono" style={{ fontSize: 12.5, color: palette.text, width: 40, textAlign: "right" }}>
              {Math.round(progress)}%
            </span>
          </div>
          {running ? (
            <div style={{ fontSize: 12.5, color: palette.textDim }}>
              Current module: <span style={{ color: palette.accent, fontWeight: 650 }}>{job.current_module ?? "Preparing…"}</span>
            </div>
          ) : (
            <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 12.5, color: palette.textDim }}>
              <span><b style={{ color: palette.text }}>{doneCount}</b> / {job.modules.length} modules completed</span>
              {failedCount > 0 && <span><b style={{ color: palette.danger }}>{failedCount}</b> failed</span>}
              <span>Total processing time <b className="mono" style={{ color: palette.text }}>{fmtDuration(totalTime)}</b></span>
            </div>
          )}
          {job.status === "partial_failed" && (
            <div style={{ fontSize: 12, color: palette.warn }}>
              Some modules failed — the pipeline ran to completion. Use Retry on the failed module.
            </div>
          )}
          {job.status === "error" && (
            <div style={{ fontSize: 12, color: palette.danger }}>{job.error ?? "Unexpected backend error."}</div>
          )}
        </div>
      </Card>

      {/* Input summary */}
      <Card title="Input" style={{ marginTop: 14 }}>
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          <Stat label="Source" value={job.source?.filename ?? "—"} mono />
          <Stat label="Packets" value={fmtCount(job.source?.n_records)} />
          <Stat label="Flows" value={fmtCount(job.source?.n_flows)} />
          <Stat label="States" value={fmtCount(job.source?.n_states)} />
          <Stat label="Elapsed" value={fmtDuration(totalTime)} mono />
        </div>
      </Card>

      {/* Module execution list */}
      <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 6 }}>
        {job.modules.map((m, idx) => {
          const isCurrent = running && job.current_module === m.id;
          const isNextUpcoming = running && m.status === "queued";
          return (
            <ModuleRow
              key={m.id}
              mod={m}
              isCurrent={isCurrent}
              showQueued={isNextUpcoming}
              onRetry={() => retryModule(m.id)}
              retryBusy={busy}
            />
          );
        })}
      </div>
    </div>
  );
}

function fmtCount(v?: number | null): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US");
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: palette.textMuted, textTransform: "uppercase", letterSpacing: 0.4 }}>{label}</div>
      <div className={mono ? "mono" : ""} style={{ fontSize: 13, color: palette.text }}>{value}</div>
    </div>
  );
}

function ModuleRow({
  mod,
  isCurrent,
  showQueued,
  onRetry,
  retryBusy,
}: {
  mod: ModelTestRunJob["modules"][number];
  isCurrent: boolean;
  showQueued: boolean;
  onRetry: () => void;
  retryBusy: boolean;
}) {
  const ok = mod.status === "ok";
  const failed = mod.status === "failed";
  const statusColor = ok ? palette.good : failed ? palette.danger : isCurrent ? palette.accent : palette.textMuted;
  const icon = ok ? "✓" : failed ? "⚠" : isCurrent ? "●" : "○";

  return (
    <Card style={{ margin: 0 }} bodyStyle={{}}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ color: statusColor, width: 14, fontSize: 13 }}>{icon}</span>
        <div style={{ flex: "1 1 200px", minWidth: 140 }}>
          <div style={{ fontSize: 13, fontWeight: 650, color: palette.text }}>
            {mod.name}
            {isCurrent && <Pill tone="accent" >running</Pill>}
            {showQueued && <Pill>queued</Pill>}
          </div>
          <div style={{ fontSize: 10.5, color: palette.textMuted }}>{mod.description}</div>
        </div>

        {failed && (
          <button
            onClick={onRetry}
            disabled={retryBusy}
            style={{
              border: `1px solid ${palette.warn}66`, color: palette.warn,
              background: "transparent", fontSize: 11.5, padding: "4px 12px", borderRadius: 6,
            }}
          >
            {retryBusy ? "Retrying…" : "Retry Module"}
          </button>
        )}

        {failed && mod.message && <span style={{ fontSize: 11, color: palette.danger }}>{mod.message}</span>}
      </div>

      {ok && (
        <div style={{ marginTop: 10 }}>
          {mod.metrics && Object.keys(mod.metrics).length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 18px" }}>
              {Object.entries(mod.metrics).map(([k, v]) => (
                <span key={k} style={{ fontSize: 11.5, color: palette.textDim }}>
                  {k.replace(/_/g, " ")}{" "}
                  <b className="mono" style={{ color: palette.text }}>{fmtVal(v)}</b>
                </span>
              ))}
            </div>
          )}
          {Array.isArray(mod.steps) && mod.steps.length > 0 && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 3 }}>
              {mod.steps.map((s) => (
                <div key={String(s.step)} style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: palette.textDim }}>
                  <span>t+{String(s.step)} · <span style={{ color: stageColor(String(s.stage)), fontWeight: 600 }}>{String(s.stage)}</span></span>
                  <span className="mono">risk {fmtVal(Number(s.risk))}</span>
                </div>
              ))}
            </div>
          )}
          {Array.isArray(mod.trajectory) && mod.trajectory.length > 0 && (
            <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
              {mod.trajectory.map((t, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: 10.5, padding: "2px 8px", borderRadius: 999,
                    background: "rgba(56,189,248,0.12)", border: "1px solid rgba(56,189,248,0.35)",
                    color: "#38bdf8",
                  }}
                >
                  {t.stage} · {t.technique_id}
                </span>
              ))}
            </div>
          )}
          {mod.graph && (mod.graph.nodes?.length || mod.graph.stage_nodes?.length) ? (
            <div style={{ marginTop: 8 }}>
              <VisualizationBoundary label={`ModelTest:${mod.id}`}>
                <AttackGraphView graph={mod.graph} />
              </VisualizationBoundary>
            </div>
          ) : null}
          {mod.recommendation && (
            <div style={{ marginTop: 8, fontSize: 11.5, color: palette.textDim }}>
              Recommendation: <span style={{ color: palette.accent, fontWeight: 650 }}>
                {String((mod.recommendation as unknown as Record<string, unknown>).recommended_label ?? "—")}
              </span>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function fmtVal(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return Number.isInteger(n) ? String(n) : n.toFixed(3);
}