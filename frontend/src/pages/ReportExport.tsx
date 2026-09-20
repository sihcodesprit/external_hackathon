import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { palette } from "../styles/theme";
import { api } from "../services/api";
import { useFetch } from "../hooks/useFetch";
import type { ReportDocument } from "../types";
import { Card, Grid, KeyValue, Tag, Pill } from "../components/ui/primitives";
import { Button } from "../components/ui/Button";
import { ErrorState, PageLoader, EmptyState } from "../components/ui/displays";
import { ThreatHeader } from "../components/analysis/ThreatHeader";
import { fmtInt, fmtNum, fmtDateTime } from "../utils/format";
import { threatGaugeColor } from "../styles/theme";

export default function ReportExport({ bare = false }: { bare?: boolean } = {}) {
  const [params] = useSearchParams();
  const jobId = params.get("job") ?? undefined;
  const { data, loading, error, refresh } = useFetch(() => api.rawReport(jobId), [jobId]);
  const [downloaded, setDownloaded] = useState(false);

  const report: ReportDocument | null = data;

  const download = async () => {
    const res = await fetch(`/api/report${jobId ? `/${jobId}` : ""}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `netwatch-report-${jobId?.slice(0, 8) ?? "current"}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    setDownloaded(true);
  };

  return (
    <div>
      {!bare && (
        <>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>Investigation Report</h1>
          <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
            Printable structured investigation document assembled from the analysis pipeline.
          </p>
        </>
      )}

      {error && <ErrorState message={error} />}
      {loading && <PageLoader label="Assembling report…" />}
      {!loading && !error && report?.status === "empty" && (
        <EmptyState
          title="No analysis to report"
          hint="Load a capture, run a scenario, or open a history entry to assemble a report."
        />
      )}

      {!loading && !error && report && report.status === "ok" && report.threat && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Pill tone={report.threat.threat_level === "CRITICAL" || report.threat.threat_level === "HIGH" ? "danger" : report.threat.threat_level === "MEDIUM" ? "warn" : "good"}>
                {report.threat.threat_level}
              </Pill>
              <span className="mono" style={{ fontSize: 12.5, color: palette.textDim }}>{report.threat.threat_status}</span>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <Button onClick={refresh} variant="ghost" size="sm">↻ Refresh</Button>
              <Button onClick={download} size="sm">{downloaded ? "Downloaded ✓" : "Download JSON"}</Button>
            </div>
          </div>

          <Card title="Threat assessment" subtitle={report.threat.summary}>
            <Grid cols="repeat(4, 1fr)" gap={20} style={{ marginTop: 6 }}>
              <KV k="Filename" v={report.file?.filename as string ?? "—"} mono />
              <KV k="Members" v={report.file?.member as string ?? "—"} mono />
              <KV k="Records / states" v={`${fmtInt(report.traffic_summary?.n_packets)} / ${fmtInt(report.traffic_summary?.n_states)}`} mono />
              <KV k="Generated" v={fmtDateTime(report.generated_at)} mono />
            </Grid>
            <div style={{ height: 10 }} />
            <Grid cols="repeat(auto-fit, minmax(150px, 1fr))" gap={12}>
              <MiniRow k="Consensus score" v={fmtNum(report.threat.consensus_score, 1)} w />
              <MiniRow k="Agreement" v={`${report.threat.agreement_count ?? "—"}/8`} w />
              <MiniRow k="Current risk" v={fmtNum(report.threat.current_risk, 2)} w />
              <MiniRow k="Forecast risk" v={fmtNum(report.threat.forecast_risk, 2)} w />
              <MiniRow k="Current stage" v={report.threat.current_stage} w />
              <MiniRow k="Predicted stage" v={report.threat.predicted_stage ?? "—"} w />
            </Grid>
          </Card>

          {report.mitre_trajectory && report.mitre_trajectory.length > 0 && (
            <Card title="MITRE trajectory" subtitle="Predicted stage → tactic → technique">
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {report.mitre_trajectory.map((t, i) => (
                  <div key={i} style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
                    <span className="mono" style={{ fontSize: 11, color: palette.textMuted, width: 40 }}>{i === 0 ? "now" : `t+${i}`}</span>
                    <span style={{ fontSize: 12.5, color: palette.text, width: 190 }}>{t.stage}</span>
                    <span style={{ fontSize: 11.5, color: palette.textDim, flex: 1 }}>{t.tactic}</span>
                    <Tag color="#38bdf8">{t.technique_id}</Tag>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {report.recommendation && (
            <Card title="Recommended response" subtitle="From both recommendation engines">
              <Grid cols="1fr 1fr" gap={20}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 650, color: palette.accent, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8 }}>Ensemble consensus</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: palette.accent }}>
                    {String((report.recommendation.ensemble as Record<string, unknown> | undefined)?.recommended_action ?? "—").replace(/_/g, " ")}
                  </div>
                  {String((report.recommendation.ensemble as Record<string, unknown> | undefined)?.reason ?? "") && (
                    <div style={{ fontSize: 12, color: palette.textDim, marginTop: 6 }}>
                      {String((report.recommendation.ensemble as Record<string, unknown> | undefined)?.reason)}
                    </div>
                  )}
                </div>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 650, color: palette.accent, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8 }}>Counterfactual sim</div>
                  <div style={{ fontSize: 14.5, fontWeight: 700, color: palette.good }}>
                    {String((report.recommendation.counterfactual as Record<string, unknown> | undefined)?.recommended_label ?? "—")}
                  </div>
                  <div style={{ fontSize: 12, color: palette.textMuted, marginTop: 6 }}>
                    {String((report.recommendation.counterfactual as Record<string, unknown> | undefined)?.reason ?? "")}
                  </div>
                </div>
              </Grid>
            </Card>
          )}

          {report.attack_graph && report.attack_graph.counts?.nodes > 0 && (
            <Card title="Predicted transition graph" subtitle={`${report.attack_graph.counts.nodes} stages, ${report.attack_graph.counts.edges} transitions`}>
              <div className="mono" style={{ fontSize: 12, color: palette.textDim, lineHeight: 1.7 }}>
                {report.attack_graph.nodes.map((n) => n.label).join(" → ")}
              </div>
            </Card>
          )}

          <Card title="Data overview" subtitle="What the report covers">
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {report.traffic_summary?.protocols?.map((p) => (
                <KeyValue key={p.protocol} k={p.protocol} v={fmtInt(p.count)} mono />
              ))}
              {report.traffic_summary?.stages_present?.map((s) => (
                <KeyValue key={s.stage} k={`stage: ${s.stage}`} v={fmtInt(s.count)} mono />
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function KV({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: palette.textMuted, letterSpacing: 0.5, textTransform: "uppercase" }}>{k}</div>
      <div className={mono ? "mono" : ""} style={{ fontSize: 12.5, color: palette.text, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v}</div>
    </div>
  );
}

function MiniRow({ k, v, w }: { k: string; v: string; w?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: palette.textMuted, letterSpacing: 0.5, textTransform: "uppercase" }}>{k}</div>
      <div className={w ? "mono" : ""} style={{ fontSize: 15, fontWeight: 650, color: palette.text, marginTop: 3 }}>{v}</div>
    </div>
  );
}