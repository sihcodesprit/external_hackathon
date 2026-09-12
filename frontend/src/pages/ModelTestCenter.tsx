import { useState, useEffect } from "react";
import { palette } from "../styles/theme";
import { api } from "../services/api";
import type { ModuleTestInfo, ModuleTestResult } from "../types";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card, Grid, Pill, Tag } from "../components/ui/primitives";
import { Button } from "../components/ui/Button";
import { ErrorState, PageLoader } from "../components/ui/displays";
import { useFetch } from "../hooks/useFetch";
import { AttackGraphView } from "../components/charts/AttackGraphView";
import { fmtNum } from "../utils/format";

export default function ModelTestCenter() {
  const { data, loading, error } = useFetch(() => api.testModules(), []);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ModuleTestResult>>({});

  const modules: ModuleTestInfo[] = data ?? [];

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
    for (const m of modules) {
      if (!m.has_data) continue;
      setRunningId(m.id);
      try {
        const res = await api.runTestModule(m.id);
        setResults((r) => ({ ...r, [m.id]: res }));
      } catch (e) {
        setResults((r) => ({ ...r, [m.id]: { status: "error", module: m.id, message: "failed" } as ModuleTestResult }));
      }
      setRunningId(null);
    }
  };

  if (loading) return <PageLoader label="Loading model modules…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Model Test Center</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Run each module against the loaded capture to validate the software-defined model stack.
      </p>

      <ControllerToast modules={modules} resultCount={Object.keys(results).length}>
        <div style={{ display: "flex", gap: 10 }}>
          <Button onClick={runAll} disabled={runningId !== null || modules.every((m) => !m.has_data)} loading={runningId !== null}>
            Run all modules
          </Button>
        </div>
      </ControllerToast>

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
    </div>
  );
}

function ControllerToast({ children }: { children: React.ReactNode; modules: ModuleTestInfo[]; resultCount: number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 4 }}>
      <span style={{ fontSize: 12, color: palette.textDim }}>
        {children}
      </span>
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
            <AttackGraphView graph={result.graph} />
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