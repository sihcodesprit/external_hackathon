import { useNavigate } from "react-router-dom";
import { palette } from "../styles/theme";
import { api } from "../services/api";
import { useFetch } from "../hooks/useFetch";
import type { HistoryEntry } from "../types";
import { Card, Tag } from "../components/ui/primitives";
import { ErrorState, PageLoader } from "../components/ui/displays";
import { fmtDateTime, fmtInt } from "../utils/format";
import { threatGaugeColor } from "../styles/theme";

export default function History() {
  const { data, loading, error, refresh } = useFetch(() => api.history(), []);
  const navigate = useNavigate();
  const entries: HistoryEntry[] = data ?? [];

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Analysis History</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Completed analyses with their threat consensus summary. Click any row to open its report.
      </p>

      {error && <ErrorState message={error} />}
      {loading && <PageLoader label="Loading history…" />}
      {!loading && !error && (
        <Card
          title={`Recent analyses (${entries.length})`}
          headerRight={
            <span style={{ cursor: "pointer", fontSize: 12, color: palette.accent }} onClick={refresh}>
              ↻ refresh
            </span>
          }
        >
          {entries.length === 0 ? (
            <div style={{ fontSize: 12.5, color: palette.textMuted }}>
              No analyses recorded yet. Upload a capture or run a scenario.
            </div>
          ) : (
            <div style={{ maxHeight: 560, overflowY: "auto", border: `1px solid ${palette.borderSoft}`, borderRadius: 8 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ textAlign: "left" }}>
                    <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>When</th>
                    <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>Source</th>
                    <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>Threat</th>
                    <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>Score</th>
                    <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>Stage</th>
                    <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>States</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => {
                    const color = threatGaugeColor(e.threat_level);
                    return (
                      <tr
                        key={e.id}
                        onClick={() => navigate(`/report?job=${e.id}`)}
                        style={{ cursor: "pointer", borderBottom: `1px solid ${palette.borderSoft}`, transition: "background 120ms" }}
                        onMouseEnter={(ev) => { (ev.currentTarget as HTMLTableRowElement).style.background = "rgba(16,24,42,0.4)"; }}
                        onMouseLeave={(ev) => { (ev.currentTarget as HTMLTableRowElement).style.background = "transparent"; }}
                      >
                        <td className="mono" style={{ padding: "8px 10px", color: palette.textDim }}>
                          {fmtDateTime(e.created_at)}
                        </td>
                        <td style={{ padding: "8px 10px", color: palette.text, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={e.filename ?? undefined}>
                          <span style={{ fontSize: 11, color: palette.textMuted }}>{e.source === "SYNTHETIC DATA" ? "synthetic · " : ""}</span>
                          {e.member ?? e.filename ?? e.source ?? "—"}
                        </td>
                        <td style={{ padding: "8px 10px" }}>
                          <Tag color={color}>{e.threat_level}</Tag>
                        </td>
                        <td className="mono" style={{ padding: "8px 10px", color }}>{(e.consensus_score ?? 0).toFixed(1)}</td>
                        <td style={{ padding: "8px 10px", color: palette.textDim }}>
                          {e.current_stage}
                          {e.predicted_stage && e.predicted_stage !== e.current_stage && (
                            <span className="mono" style={{ color: palette.textMuted }}> → {e.predicted_stage}</span>
                          )}
                        </td>
                        <td className="mono" style={{ padding: "8px 10px", color: palette.textDim }}>{fmtInt(e.n_states)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}