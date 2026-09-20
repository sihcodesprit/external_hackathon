import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { api } from "../services/api";
import { useFetch } from "../hooks/useFetch";
import type { ScenarioInfo } from "../types";
import { Card, Pill, Grid, Tag } from "../components/ui/primitives";
import { Button } from "../components/ui/Button";
import { ErrorState, PageLoader } from "../components/ui/displays";

export default function Scenarios({ bare = false }: { bare?: boolean } = {}) {
  const { data, loading, error } = useFetch(() => api.scenarios(), []);
  const { startScenario, running, sourceLabel } = useAnalysis();
  const scenarios: ScenarioInfo[] = data ?? [];

  const activeKind = ["benign", "recon", "bruteforce", "dos", "mixed"];

  const activeScenario =
    running && sourceLabel?.startsWith("scenario:") ? sourceLabel.slice("scenario:".length) : null;

  return (
    <div>
      {!bare && (
        <>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Attack Scenarios</h1>
          <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
            Built-in demos that feed the engine with{" "}
            <span style={{ color: palette.warn, fontWeight: 650 }}>clearly-labelled SYNTHETIC DATA</span> —
            they are generated traces and are never presented as live captures.
          </p>
        </>
      )}

      <div style={{ marginBottom: 16, display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 12px", borderRadius: 8, border: `1px solid ${palette.warn}40`, background: `${palette.warn}10` }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: palette.warn }} />
        <span style={{ fontSize: 11.5, fontWeight: 600, color: palette.warn, letterSpacing: 0.6 }}>SOURCE: SYNTHETIC DATA</span>
      </div>

      {error && <ErrorState message={error} />}
      {loading && <PageLoader label="Loading scenarios…" />}
      {!loading && !error && (
        <Grid cols="repeat(auto-fill, minmax(300px, 1fr))" gap={14}>
          {scenarios.map((s, i) => (
            <Card
              key={s.id}
              title={s.name}
              subtitle={`scenario ${i + 1} / ${scenarios.length}`}
              headerRight={<Pill tone="warn">synthetic</Pill>}
            >
              <div style={{ fontSize: 12.5, color: palette.textDim, lineHeight: 1.6, marginBottom: 14, minHeight: 46 }}>
                {s.description}
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
                {(s.attack_types?.length ? s.attack_types : ["none"]).map((a) => (
                  <Tag key={a} color={a === "none" ? "#34d399" : "#f87171"}>
                    {a}
                  </Tag>
                ))}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="mono" style={{ fontSize: 11, color: palette.textMuted }}>{s.id}</span>
                <Button
                  size="sm"
                  onClick={() => startScenario(s.id)}
                  disabled={running}
                  loading={activeScenario === s.id}
                  variant={activeKind.includes(s.id) && i % 2 === 1 ? "outline" : "primary"}
                >
                  {activeScenario === s.id ? "Running…" : "Run scenario"}
                </Button>
              </div>
            </Card>
          ))}
        </Grid>
      )}

      {!loading && !error && scenarios.length === 0 && (
        <div style={{ fontSize: 12.5, color: palette.textMuted }}>
          The scenario manifest is empty on the backend.
        </div>
      )}
    </div>
  );
}