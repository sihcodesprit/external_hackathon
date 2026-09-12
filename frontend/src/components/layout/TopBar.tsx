import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { palette } from "../../styles/theme";
import { api } from "../../services/api";
import { useAnalysis } from "../../store/analysisContext";
import { Dot } from "../ui/primitives";
import { fmtClock } from "../../utils/format";

export function TopBar() {
  const navigate = useNavigate();
  const { job, running, doc, sourceLabel } = useAnalysis();
  const [uptime, setUptime] = useState(0);
  const [started, setStarted] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(() => undefined)
      .catch(() => undefined);
    setInterval(() => {}, 1000);
    api
      .systemInfo()
      .then((s) => {
        setUptime(s.uptime_seconds);
        setStarted(s.started_at);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!started) return;
    const id = window.setInterval(
      () => setUptime(Math.floor((Date.now() - new Date(started).getTime()) / 1000)),
      5000,
    );
    return () => window.clearInterval(id);
  }, [started]);

  const hhmmss = (v: number) =>
    `${String(Math.floor(v / 3600)).padStart(2, "0")}:${String(Math.floor((v % 3600) / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;

  return (
    <header
      style={{
        height: 52,
        position: "sticky",
        top: 0,
        zIndex: 30,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "0 20px",
        background: "rgba(5,8,16,0.82)",
        backdropFilter: "blur(10px)",
        borderBottom: `1px solid ${palette.borderSoft}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
        <span
          style={{ fontSize: 16, cursor: "pointer", color: palette.text }}
          onClick={() => navigate("/")}
          title="Home"
        >
          ◈
        </span>
        <div
          className="mono"
          style={{
            fontSize: 11,
            color: palette.textMuted,
            border: `1px solid ${palette.borderSoft}`,
            borderRadius: 6,
            padding: "3px 8px",
          }}
        >
          uptime {hhmmss(uptime)}
        </div>
        <div
          className="mono"
          style={{ fontSize: 11, color: palette.textMuted, display: "none" }}
        >
          {started ? fmtClock(started) : "…"}
        </div>
      </div>

      <div style={{ flex: 1, overflow: "hidden", padding: "0 10px" }}>
        {running && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <Dot color={palette.warn} />
            <span className="mono" style={{ fontSize: 11.5, color: palette.textDim, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {job ? `${job.stage} — ${job.progress}%` : "processing…"}
            </span>
            <div style={{ flex: 1, height: 3, background: palette.border, borderRadius: 99, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${job?.progress ?? 5}%`,
                  background: "linear-gradient(90deg,#0ea5e9,#22d3ee)",
                  transition: "width 700ms ease",
                }}
              />
            </div>
          </div>
        )}
        {!running && doc && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <Dot color={palette.good} />
            <span style={{ fontSize: 11.5, color: palette.textDim, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              Active analysis: <span className="mono">{sourceLabel ?? (doc.member ?? doc.filename)}</span> ·{" "}
              {doc.n_states} states
            </span>
          </div>
        )}
        {!running && !doc && (
          <span style={{ fontSize: 11.5, color: palette.textMuted }}>
            Load a capture to start the analysis engine.
          </span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Dot color={palette.good} />
        <span style={{ fontSize: 11.5, color: palette.textDim }}>Engine live</span>
      </div>
    </header>
  );
}