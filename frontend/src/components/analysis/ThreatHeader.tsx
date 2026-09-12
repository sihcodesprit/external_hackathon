import { palette } from "../../styles/theme";
import type { AnalysisDoc, EnsembleConsensus, ThreatLevel } from "../../types";
import { fmtNum } from "../../utils/format";
import { threatGaugeColor } from "../../styles/theme";

export function ThreatHeader({ doc }: { doc: AnalysisDoc }) {
  const ens = doc.ensemble?.consensus;
  const threat: ThreatLevel = ens?.threat_level ?? "BENIGN";
  const score = ens?.score ?? 0;
  const color = threatGaugeColor(threat);

  return (
    <div className="card" style={{ borderColor: `${color}45` }}>
      <div style={{ display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap" }}>
        <SemiGauge color={color} threat={threat} score={score} />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: color,
                boxShadow: `0 0 14px ${color}90`,
              }}
            />
            <span
              style={{
                fontSize: 18,
                fontWeight: 700,
                color,
                letterSpacing: 0.6,
              }}
            >
              {threat}
            </span>
            <span
              className="mono"
              style={{ fontSize: 12, color: palette.textDim, marginLeft: 4 }}
            >
              {fmtNum(score, 1)}
            </span>
          </div>
          {ens?.recommendation && (
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <span
                style={{
                  padding: "3px 10px",
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: 0.5,
                  textTransform: "uppercase",
                  color: ens.recommendation.projected_risk_reduction_pct > 40 ? palette.accent : palette.textDim,
                  background: ens.recommendation.projected_risk_reduction_pct > 40 ? palette.accentSoft : "transparent",
                  border: `1px solid ${ens.recommendation.projected_risk_reduction_pct > 40 ? palette.accentBorder : palette.borderSoft}`,
                }}
              >
                {ens.recommendation.action_label || ens.recommendation.recommended_action.replace(/_/g, " ")}
              </span>
              <span style={{ fontSize: 11.5, color: palette.textDim }}>
                {ens.agreement_count ?? 0} / {ens.total_detectors ?? 8} detectors aligned
              </span>
              {ens.primary_stage && (
                <span style={{ fontSize: 11.5, color: palette.textMuted }}>
                  primary stage: <span style={{ color: palette.text }}>{ens.primary_stage}</span>
                </span>
              )}
            </div>
          )}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
          <div style={{ display: "flex", gap: 20 }}>
            <MiniStat label="Records" value={doc.n_records} />
            <MiniStat label="States" value={doc.n_states} />
          </div>
          <div style={{ fontSize: 11, color: palette.textMuted, marginTop: 2 }}>
            {doc.filename ?? "—"}{doc.member ? ` · ${doc.member}` : ""}
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div className="mono" style={{ fontSize: 16, fontWeight: 650, color: palette.text }}>
        {value.toLocaleString()}
      </div>
      <div style={{ fontSize: 10, color: palette.textMuted, letterSpacing: 0.5, textTransform: "uppercase" }}>
        {label}
      </div>
    </div>
  );
}

function SemiGauge({ color, threat, score }: { color: string; threat: string; score: number }) {
  const pct = Math.min(1, score / 100);
  const r = 44;
  const circ = Math.PI * r;
  const offset = circ * (1 - pct);

  return (
    <svg width="120" height="80" viewBox="0 0 120 80" style={{ overflow: "visible" }}>
      <g transform="translate(60, 68)">
        <path
          d={`M ${-r} 0 A ${r} ${r} 0 0 1 ${r} 0`}
          fill="none"
          stroke={palette.border}
          strokeWidth={10}
          strokeLinecap="round"
        />
        <path
          d={`M ${-r} 0 A ${r} ${r} 0 0 1 ${r} 0`}
          fill="none"
          stroke={color}
          strokeWidth={10}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{
            transition: "stroke-dashoffset 800ms ease, stroke 500ms",
            filter: `drop-shadow(0 0 10px ${color}60)`,
          }}
        />
        <text
          x={0}
          y={-6}
          textAnchor="middle"
          fill={palette.text}
          fontSize={16}
          fontWeight={700}
          fontFamily="ui-monospace, monospace"
        >
          {score.toFixed(0)}
        </text>
        <text
          x={0}
          y={10}
          textAnchor="middle"
          fill={palette.textDim}
          fontSize={8}
          letterSpacing={1.2}
          textTransform="uppercase"
          fontFamily="ui-monospace, monospace"
        >
          THREAT
        </text>
      </g>
    </svg>
  );
}