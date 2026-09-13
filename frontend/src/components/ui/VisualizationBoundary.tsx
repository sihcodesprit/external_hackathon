import { Component, type ReactNode } from "react";
import { palette } from "../../styles/theme";

interface Props {
  children: ReactNode;
  label?: string;
}

interface State {
  error: Error | null;
}

export class VisualizationBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error): void {
    console.error("[VisualizationBoundary]", this.props.label ?? "visualization", error);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            padding: "18px 16px", borderRadius: 10,
            border: `1px solid ${palette.border}`, background: "rgba(16,24,42,0.6)",
            display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start",
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 650, color: palette.text }}>Visualization unavailable</span>
          <span style={{ fontSize: 11.5, color: palette.textDim }}>
            The analysis data is still available. Try refreshing the visualization.
          </span>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              border: `1px solid ${palette.accentBorder}`, color: palette.accent,
              background: "transparent", fontSize: 11.5, padding: "4px 12px", borderRadius: 6,
            }}
          >
            Retry visualization
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}