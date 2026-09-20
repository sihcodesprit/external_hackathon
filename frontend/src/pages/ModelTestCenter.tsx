import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { palette } from "../styles/theme";
import { api } from "../services/api";
import type { ModuleTestInfo, ModuleTestResult, ModelTestJobSummary } from "../types";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card, Pill, Tag } from "../components/ui/primitives";
import { Button } from "../components/ui/Button";
import { ErrorState, PageLoader } from "../components/ui/displays";
import { useFetch } from "../hooks/useFetch";
import { VisualizationBoundary } from "../components/ui/VisualizationBoundary";
import { AttackGraphView } from "../components/charts/AttackGraphView";
import { fmtNum } from "../utils/format";

export default function ModelTestCenter({ bare = false }: { bare?: boolean } = {}) {
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useFetch(() => api.testModules(), []);
  const jobsFetcher = useFetch<ModelTestJobSummary[]>(() => api.modelTestJobs(), []);
  const { doc } = useAnalysis();

  const [runningId, setRunningId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ModuleTestResult>>({});
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const modules: ModuleTestInfo[] = data ?? [];
  const hasAnyData = modules.some((m) => m.has_data);

  const run = async (id: string) => {
    setRunningId(id);
    try {
      const res = await api.runTestModule(id);
      setResults((r) => ({ ...r, [id]: res }));
    } catch (e) {
      setResults((r) => ({
        ...r,
        [id]: { status: "error", module: id, message: e instanceof Error ? e.message : String(e) },
      }));
    } finally {
      setRunningId(null);
    }
  };

  const runAll = async () => {
    if (starting || runningId !== null) return;
    setStarting(true);
    setStartError(null);
    try {
      const { job_id } = await api.createModelTestJob();
      navigate(`/validate?tab=model-run&job=${job_id}`);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : String(e));
      setStarting(false);
    }
  };

  if (loading) return <PageLoader label="Loading model modules…" />;
  if (error) return <ErrorState message={error} />;

  const currentJob = doc
    ? { filename: doc.member ?? doc.filename ?? "capture", packets: doc.n_records ?? 0, states: doc.n_states ?? 0 }
    : null;

  return (
    <div>
      {!bare && (
        <>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Model Test Center</h1>
          <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
            Test every AI module independently or run the full pipeline against the loaded capture.
          </p>
        </>
      )}

      <Card title={"Input"}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
            {currentJob ? (
              <>
                <div>
                  <div style={{ fontSize: 10.5, color: palette.textMuted, textTransform: "uppercase", letterSpacing: 0.4 }}>Capture</div>
                  <div className="mono" style={{ fontSize: 12.5, color: palette.text }}>{currentJob.filename}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10.5, color: palette.textMuted, textTransform: "uppercase", letterSpacing: 0.4 }}>Records</div>
                  <div className="mono" style={{ fontSize: 12.5, color: palette.text }}>{fmtNum(currentJob.packets, 0)} packets</div>
                </div>
                <div>
                  <div style={{ fontSize: 10.5, color: palette.textMuted, textTransform: "uppercase", letterSpacing: 0.4 }}>States</div>
                  <div className="mono" style={{ fontSize: 12.5, color: palette.text }}>{currentJob.states}</div>
                </div>
              </>
            ) : (
              <span style={{ fontSize: 12, color: palette.textMuted }}>
                Load a capture or run a scenario to populate the module inputs.
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Button
              onClick={runAll}
              disabled={starting || !hasAnyData || runningId !== null}
              loading={starting}
            >
              Run All Modules
            </Button>
            <span style={{ fontSize: 11.5, color: palette.textMuted }}>
              {starting ? "Starting…" : ""}
            </span>
          </div>
        </div>
        {startError && <div style={{ marginTop: 10, fontSize: 12, color: palette.danger }}>⚠ {startError}</div>}
      </Card>

      {jobsFetcher.data && jobsFetcher.data.length > 0 && (
        <Card title="Recent runs" style={{ marginTop: 14 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {jobsFetcher.data.slice(0, 8).map((job) => (
              <Link
                key={job.job_id}
                to={`/validate?tab=model-run&job=${job.job_id}`}
                style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
                  padding: "7px 10px", borderRadius: 8, background: "rgba(16,24,42,0.5)",
                  border: `1px solid ${palette.borderSoft}`,
                }}
              >
                <span className="mono" style={{ fontSize: 11.5, color: palette.text }}>
                  {job.job_id}
                </span>
                <span style={{ fontSize: 11.5, color: palette.textDim, flex: 1 }}>
                  {job.source?.filename ?? "capture"}
                </span>
                <Pill tone={job.status === "completed" ? "good" : job.status === "partial_failed" ? "warn" : job.status === "failed" ? "danger" : "warn"}>
                  {job.status}
                </Pill>
                <span className="mono" style={{ fontSize: 11, color: palette.textMuted }}>
                  {job.progress}%
                </span>
              </Link>
            ))}
          </div>
        </Card>
      )}

      <RequireAnalysis hint="The test center runs each module against live analysis data — load a capture or scenario first.">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 14, marginTop: 16 }}>
          {modules.map((m) => (
            <ModuleCard
              key={m.id}
              module={m}
              result={results[m.id]}
              running={runningId === m.id}
              onRun={() => run(m.id)}
            />
          ))}
        </div>
      </RequireAnalysis>

      <div style={{ marginTop: 8 }}>
        <button
          onClick={refresh}
          style={{ border: "none", background: "transparent", color: palette.textMuted, fontSize: 11.5, cursor: "pointer" }}
        >
          Refresh module availability
        </button>
      </div>
    </div>
  );
}

function ModuleCard({
  module,
  result,
  running,
  onRun,
}: {
  module: ModuleTestInfo;
  result?: ModuleTestResult;
  running: boolean;
  onRun: () => void;
}) {
  const ok = result?.status === "ok";
  const metrics = (result?.metrics ?? {}) as Record<string, number> | undefined;

  return (
    <Card
      title={module.name}
      subtitle={module.description}
      headerRight={<Pill tone={module.has_data ? "good" : "warn"}>{module.has_data ? "ready" : "no data"}</Pill>}
      glow
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 11, color: palette.textMuted }}>{module.id}</span>
        <Button size="sm" variant={result ? "outline" : "primary"} onClick={onRun} disabled={running || !module.has_data} loading={running}>
          {running ? "Running…" : ok ? "Re-run" : "Run test"}
        </Button>
      </div>
      <div style={{ marginTop: 12 }}>
        {!result && running && <Spin />}
        {!result && !running && !module.has_data && (
          <div style={{ fontSize: 12, color: palette.textMuted }}>Module requires loaded analysis data.</div>
        )}
        {!result && !running && module.has_data && (
          <div style={{ fontSize: 12, color: palette.textMuted }}>Not executed yet.</div>
        )}
        {result?.status === "error" && (
          <div style={{ fontSize: 12, color: palette.danger }}>⚠ {result.message}</div>
        )}
        {ok && metrics && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {Object.entries(metrics).map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ fontSize: 12, color: palette.textDim }}>{k.replace(/_/g, " ")}</span>
                <span className="mono" style={{ fontSize: 12, color: palette.text }}>{fmtNum(v, 3)}</span>
              </div>
            ))}
          </div>
        )}
        {ok && Array.isArray(result?.steps) && (
          <div style={{ marginTop: 8 }}>
            {result.steps!.map((s) => (
              <div key={String(s.step)} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: palette.textDim }}>
                <span>t+{String(s.step)} · {String(s.stage)}</span>
                <span className="mono">{fmtNum(Number(s.risk), 3)}</span>
              </div>
            ))}
          </div>
        )}
        {ok && Array.isArray(result?.trajectory) && (
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
            {result.trajectory!.map((t, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ fontSize: 12, color: palette.textDim }}>{t.stage}</span>
                <Tag color="#38bdf8">{t.technique_id}</Tag>
              </div>
            ))}
          </div>
        )}
        {ok && result?.graph && (
          <div style={{ marginTop: 8 }}>
            <VisualizationBoundary label={`ModuleCard:${module.id}`}>
              <AttackGraphView graph={result.graph} />
            </VisualizationBoundary>
          </div>
        )}
        {ok && result?.recommendation && (
          <div style={{ marginTop: 8, fontSize: 12, color: palette.textDim }}>
            Recommendation: <span style={{ color: palette.accent, fontWeight: 650 }}>
              {String((result.recommendation as unknown as Record<string, unknown>).recommended_label ?? "—")}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}

function Spin() {
  return <div style={{ display: "flex", gap: 8, alignItems: "center" }}><span className="loading-spinner" style={{ width: 12, height: 12 }} /><span style={{ fontSize: 11.5, color: palette.textDim }}>executing…</span></div>;
}