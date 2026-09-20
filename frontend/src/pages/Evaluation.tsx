import { palette } from "../styles/theme";
import { api } from "../services/api";
import { useFetch } from "../hooks/useFetch";
import { Card, Grid, KeyValue } from "../components/ui/primitives";
import { ErrorState, PageLoader } from "../components/ui/displays";

function renderValue(v: unknown, depth: number): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(4);
  return String(v);
}

function DictView({ data, depth = 0 }: { data: Record<string, unknown>; depth?: number }) {
  if (depth > 3) return <span style={{ fontSize: 11, color: palette.textMuted }}>…</span>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {Object.entries(data).map(([k, v]) => {
        if (v && typeof v === "object" && !Array.isArray(v)) {
          return (
            <div key={k}>
              <div style={{ fontSize: 11.5, fontWeight: 650, color: palette.accent, textTransform: "uppercase", letterSpacing: 0.6, margin: "8px 0 4px" }}>
                {k.replace(/_/g, " ")}
              </div>
              <div style={{ paddingLeft: 10 }}>
                <DictView data={v as Record<string, unknown>} depth={depth + 1} />
              </div>
            </div>
          );
        }
        if (Array.isArray(v)) {
          if (v.length === 0) return <span key={k} style={{ fontSize: 12, color: palette.textMuted }}>{k}: []</span>;
          return (
            <div key={k}>
              <div style={{ fontSize: 11.5, fontWeight: 650, color: palette.accent, textTransform: "uppercase", letterSpacing: 0.6, margin: "8px 0 4px" }}>
                {k.replace(/_/g, " ")} ({v.length})
              </div>
              <div style={{ paddingLeft: 10 }}>
                {v.slice(0, 20).map((item, i) =>
                  item && typeof item === "object" ? (
                    <DictView key={i} data={item as Record<string, unknown>} depth={depth + 1} />
                  ) : (
                    <KeyValue key={i} k={`${k}[${i}]`} v={renderValue(item, depth)} mono />
                  ),
                )}
                {v.length > 20 && <span style={{ fontSize: 11, color: palette.textMuted }}>… {v.length - 20} more</span>}
              </div>
            </div>
          );
        }
        return <KeyValue key={k} k={k} v={renderValue(v, depth)} mono />;
      })}
    </div>
  );
}

export default function Evaluation({ bare = false }: { bare?: boolean } = {}) {
  const { data, loading, error } = useFetch(() => api.rawEvaluation(), []);

  if (loading) return <PageLoader label="Running model evaluation…" />;
  if (error) return <div style={{ display: "flex", flexDirection: "column", gap: 14 }}><ErrorState message={error} /></div>;

  const evalData: Record<string, unknown> = (data ?? {}) as Record<string, unknown>;

  return (
    <div>
      {!bare && (
        <>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Model Evaluation</h1>
          <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
            Training and predictive-metrics evaluation computed from the world model against the loaded capture.
          </p>
        </>
      )}

      {Object.keys(evalData).length === 0 ? (
        <Card title="Evaluation">
          <div style={{ fontSize: 12.5, color: palette.textMuted }}>
            No evaluation report available yet. Load a capture, then run an analysis to generate evaluation metrics
            on the reconstructed states.
          </div>
        </Card>
      ) : (
        <Grid cols="1fr" gap={14}>
          <Card title="Evaluation report" subtitle="Derived from the current model and capture">
            <DictView data={evalData} />
          </Card>
        </Grid>
      )}
    </div>
  );
}