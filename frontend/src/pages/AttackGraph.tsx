import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card } from "../components/ui/primitives";
import { AttackGraphView } from "../components/charts/AttackGraphView";
import { VisualizationBoundary } from "../components/ui/VisualizationBoundary";

export default function AttackGraph() {
  const { doc } = useAnalysis();
  const graph = doc?.graph ?? null;

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>
        Predictive Attack Graph
      </h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Forecasted progression from the World Model K-step rollout. Timeline mode shows every forecast
        step; Stage Graph collapses consecutive identical stages.
      </p>

      <RequireAnalysis>
        <VisualizationBoundary label="PredictiveAttackGraph">
          {graph && (graph.nodes?.length || graph.stage_nodes?.length) ? (
            <Card title="Predicted attack trajectory" subtitle={undefined}>
              <AttackGraphView graph={graph} />
            </Card>
          ) : (
            <Card title="Predicted attack trajectory">
              <div style={{ padding: "26px 16px", display: "flex", flexDirection: "column", gap: 6, alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 650, color: palette.text }}>No predictive attack path available</span>
                <span style={{ fontSize: 11.5, color: palette.textMuted, textAlign: "center", maxWidth: 460 }}>
                  The current model output does not contain enough information to construct a stage-transition graph.
                </span>
              </div>
            </Card>
          )}
        </VisualizationBoundary>
      </RequireAnalysis>
    </div>
  );
}