import { useState } from "react";
import { palette } from "../styles/theme";
import { useAnalysis } from "../store/analysisContext";
import { RequireAnalysis } from "../components/analysis/RequireAnalysis";
import { Card, Grid, KeyValue, Tag } from "../components/ui/primitives";
import type { NetworkStateRow } from "../types";
import { fmtNum, fmtDateTime } from "../utils/format";

export default function NetworkState() {
  const { doc } = useAnalysis();
  const [selectedIdx, setSelectedIdx] = useState<number>(-1);

  const groups = doc?.state_groups as Array<{ id: string; label: string; description: string; features: Array<{ feature: string; label: string; value: number }> }> | null;
  const rows: NetworkStateRow[] = doc?.network_state?.states ?? [];
  const sel = rows[selectedIdx >= 0 ? selectedIdx : rows.length - 1];

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Network State</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Windowed network states reconstructed from the capture, grouped into traffic, TCP handshake,
        entropy, temporal and dynamic-graph feature families.
      </p>

      <RequireAnalysis>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card title="Current state metrics" subtitle={sel ? `${fmtDateTime(sel.timestamp)} · ${sel.stage || "Benign"}` : undefined}>
            {!groups || groups.length === 0 ? (
              <div style={{ fontSize: 12.5, color: palette.textMuted }}>No feature groups available.</div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
                {groups.map((g) => (
                  <div key={g.id} style={{ padding: 12, borderRadius: 9, border: `1px solid ${palette.borderSoft}`, background: "rgba(16,24,42,0.3)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 650, color: palette.text }}>{g.label}</span>
                      <Tag color="#38bdf8">{g.features.length}</Tag>
                    </div>
                    <div style={{ fontSize: 11, color: palette.textMuted, marginBottom: 8 }}>{g.description}</div>
                    <div>
                      {g.features.map((f) => (
                        <KeyValue key={f.feature} k={f.label} v={fmtNum(f.value, 3)} mono />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title={`State timeline (${rows.length})`} subtitle="Click a row to inspect its feature vector">
            {rows.length === 0 ? (
              <div style={{ fontSize: 12.5, color: palette.textMuted }}>No states captured.</div>
            ) : (
              <div style={{ maxHeight: 380, overflowY: "auto", border: `1px solid ${palette.borderSoft}`, borderRadius: 8 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ textAlign: "left" }}>
                      <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>#</th>
                      <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>Timestamp</th>
                      <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>Label</th>
                      <th style={{ padding: "8px 10px", color: palette.textMuted, fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, borderBottom: `1px solid ${palette.border}` }}>Stage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr
                        key={r.idx}
                        onClick={() => {
                          setSelectedIdx(r.idx);
                          document.getElementById(`state-features`)?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }}
                        style={{
                          cursor: "pointer",
                          background: r.idx === sel?.idx ? palette.accentSoft : "transparent",
                          borderBottom: `1px solid ${palette.borderSoft}`,
                        }}
                      >
                        <td className="mono" style={{ padding: "7px 10px", color: palette.textDim }}>{r.idx}</td>
                        <td className="mono" style={{ padding: "7px 10px", color: palette.textDim }}>{fmtDateTime(r.timestamp)}</td>
                        <td style={{ padding: "7px 10px" }}>
                          <Tag color={r.label === 1 ? "#ef4444" : "#34d399"}>{r.label === 1 ? "Attack" : "Benign"}</Tag>
                        </td>
                        <td style={{ padding: "7px 10px", color: r.stage ? palette.text : palette.textMuted }}>
                          {r.stage || "Benign"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {sel && (
            <div id="state-features">
              <Card title={`State #${sel.idx} — full feature vector`} subtitle={fmtDateTime(sel.timestamp)}>
                <Grid cols="repeat(auto-fit, minmax(240px, 1fr))" gap={14}>
                  {(["traffic", "tcp_handshake", "entropy", "temporal", "graph"] as const).map((gk) => {
                    const vals = (sel as unknown as Record<string, Record<string, number>>)[gk] ?? {};
                    const entries = Object.entries(vals);
                    if (entries.length === 0) return null;
                    return (
                      <div key={gk}>
                        <div style={{ fontSize: 11, fontWeight: 650, color: palette.accent, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 6 }}>
                          {gk.replace("_", " ")}
                        </div>
                        {entries.map(([k, v]) => (
                          <KeyValue key={k} k={k} v={fmtNum(v, 3)} mono />
                        ))}
                      </div>
                    );
                  })}
                </Grid>
              </Card>
            </div>
          )}
        </div>
      </RequireAnalysis>
    </div>
  );
}