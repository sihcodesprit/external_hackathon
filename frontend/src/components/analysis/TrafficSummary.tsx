import { palette } from "../../styles/theme";
import type { TrafficSummary as TS } from "../../types";
import { fmtInt, fmtBytes } from "../../utils/format";
import { StatBar } from "../ui/displays";

export function TrafficSummary({ summary }: { summary: TS }) {
  if (!summary || typeof summary !== "object") return null;
  const protocols = summary.protocols ?? [];
  const maxProto = Math.max(1, ...protocols.map((p) => p.count));
  const protoColors = ["#38bdf8", "#34d399", "#fbbf24", "#c084fc", "#fb923c", "#e879f9"];

  const statRows: Array<[string, string]> = [
    ["Packets", fmtInt(summary.n_packets)],
    ["Bytes", fmtBytes(summary.n_bytes)],
    ["Flows", fmtInt(summary.n_flows)],
    ["Hosts", fmtInt(summary.n_hosts)],
  ];

  return (
    <div className="card">
      <div style={{ fontSize: 12.5, fontWeight: 600, color: palette.text, marginBottom: 14, letterSpacing: 0.2 }}>
        Traffic Summary
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
        {statRows.map(([label, value]) => (
          <div key={label} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span style={{ fontSize: 10, color: palette.textMuted, letterSpacing: 0.5, textTransform: "uppercase" }}>{label}</span>
            <span className="mono" style={{ fontSize: 15, fontWeight: 650, color: palette.text }}>{value}</span>
          </div>
        ))}
      </div>

      {protocols.length > 0 && (
        <div>
          <div style={{ fontSize: 11.5, fontWeight: 600, color: palette.textDim, marginBottom: 8 }}>Protocol distribution</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {protocols.map((p, i) => (
              <StatBar
                key={p.protocol}
                label={p.protocol || "(unknown)"}
                value={p.count}
                max={maxProto}
                color={protoColors[i % protoColors.length]}
                right={fmtInt(p.count)}
              />
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginTop: 16 }}>
        <Mini label="Attack packets" value={fmtInt(summary.attack_packets)} tone="danger" />
        <Mini label="Benign packets" value={fmtInt(summary.benign_packets)} tone="good" />
        <Mini label="Attack states" value={fmtInt(summary.attack_states)} tone="danger" />
        <Mini label="Duration" value={`${(summary.duration_seconds ?? 0).toFixed(1)}s`} />
      </div>
    </div>
  );
}

function Mini({ label, value, tone }: { label: string; value: string; tone?: "danger" | "good" }) {
  const color = tone === "danger" ? palette.danger : tone === "good" ? palette.good : palette.text;
  return (
    <div style={{ padding: "9px 11px", borderRadius: 8, border: `1px solid ${palette.borderSoft}`, background: "rgba(16,24,42,0.25)" }}>
      <div style={{ fontSize: 10, color: palette.textMuted, letterSpacing: 0.4, textTransform: "uppercase" }}>{label}</div>
      <div className="mono" style={{ fontSize: 13.5, fontWeight: 650, color, marginTop: 3 }}>{value}</div>
    </div>
  );
}