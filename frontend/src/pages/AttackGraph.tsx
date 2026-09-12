import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card } from "../components/ui/primitives";
import { AttackGraphView } from "../components/charts/AttackGraphView";

export default function AttackGraph() {
  const { doc } = useAnalysis();
  const graph = doc?.graph;

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Predictive Attack Graph</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Stage-transition graph derived from the world model rollout. Edge weights reflect the predicted
        transition confidence, node colors map to attack-stage severity.
      </p>

      <RequireAnalysis>
        <Card
          title="Assault trajectory"
          subtitle={graph?.counts ? `${graph.counts.nodes} stages · ${graph.counts.edges} transitions` : undefined}
        >
          {graph ? <AttackGraphView graph={graph} /> : <div style={{ fontSize: 12.5, color: palette.textMuted }}>No graph produced.</div>}
        </Card>

        {graph && graph.nodes.length > 0 && (
          <div
            style={{
              marginTop: 14,
              padding: "10px 14px",
              borderRadius: 8,
              background: "rgba(16,24,42,0.3)",
              border: `1px solid ${palette.borderSoft}`,
              fontSize: 12,
              color: palette.textDim,
              lineHeight: 1.6,
            }}
          >
            <span style={{ fontWeight: 650, color: palette.text }}>Interpretation: </span>
            The model predicts the network evolving through{" "}
            {graph.nodes.map((n) => n.label).join(" → ")}. The most severe stages along the path are
            rendered with the strongest color.
          </div>
        )}
      </RequireAnalysis>
    </div>
  );
}