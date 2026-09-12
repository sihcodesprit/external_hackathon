import { palette } from "../../styles/theme";
import type { JobPoll } from "../../types";

export function JobProgress({ job }: { job: JobPoll | null }) {
  const pct = Math.max(0, Math.min(100, job?.progress ?? 0));
  const error = job?.status === "error";

  return (
    <div className="card" style={{ borderColor: error ? "rgba(239,68,68,0.4)" : undefined }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {!error && <span className="loading-spinner" style={{ width: 15, height: 15 }} />}
          {error && <span style={{ color: palette.danger, fontSize: 15 }}>⚠</span>}
          <span style={{ fontSize: 13, fontWeight: 600, color: palette.text }}>{error ? "Analysis failed" : "Analysis running"}</span>
        </div>
        <span className="mono" style={{ fontSize: 12, color: error ? palette.danger : palette.accent }}>
          {error ? job?.message ?? "unknown error" : `${pct.toFixed(0)}%`}
        </span>
      </div>
      <div style={{ height: 6, background: palette.border, borderRadius: 99, overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: error ? palette.danger : "linear-gradient(90deg,#0ea5e9,#22d3ee)",
            transition: "width 700ms ease",
          }}
        />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
        <span className="mono" style={{ fontSize: 12, color: palette.textDim }}>stage: {job?.stage ?? "queued"}</span>
        <span className="mono" style={{ fontSize: 12, color: palette.textMuted }}>job {job?.job_id?.slice(0, 8) ?? "—"}</span>
      </div>
      {job?.message && (
        <div style={{ fontSize: 12, color: palette.textMuted, marginTop: 8 }}>{job.message}</div>
      )}
    </div>
  );
}