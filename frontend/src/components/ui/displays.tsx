import type { ReactNode } from "react";
import { palette, radius } from "../../styles/theme";

export function MetricCard({
  label,
  value,
  sub,
  tone = "default",
  icon,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "default" | "accent" | "danger" | "good";
  icon?: ReactNode;
}) {
  const toneMap = {
    default: palette.text,
    accent: palette.accent,
    danger: palette.danger,
    good: palette.good,
  };
  return (
    <div
      className="card"
      style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 4 }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", color: palette.textDim }}>
          {label}
        </span>
        {icon}
      </div>
      <span className="mono" style={{ fontSize: 24, fontWeight: 650, color: toneMap[tone], lineHeight: 1.1 }}>
        {value}
      </span>
      {sub && <span style={{ fontSize: 11, color: palette.textMuted }}>{sub}</span>}
    </div>
  );
}

export function StatBar({
  label,
  value,
  max,
  color,
  right,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
  right?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / Math.max(1e-9, max)) * 100));
  return (
    <div style={{ display: "grid", gridTemplateColumns: "150px 1fr 64px", gap: 10, alignItems: "center", padding: "4px 0" }}>
      <span style={{ fontSize: 12, color: palette.textDim, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={label}>
        {label}
      </span>
      <div style={{ height: 6, background: palette.border, borderRadius: radius.pill, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: radius.pill }} />
      </div>
      <span className="mono" style={{ fontSize: 11.5, color: palette.text, textAlign: "right" }}>
        {right ?? `${pct.toFixed(0)}%`}
      </span>
    </div>
  );
}

export function EmptyState({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div style={{ textAlign: "center", padding: "44px 20px" }}>
      <div style={{ fontSize: 26, marginBottom: 10, opacity: 0.6 }}>◎</div>
      <div style={{ fontSize: 14, color: palette.text, fontWeight: 600 }}>{title}</div>
      {hint && <div style={{ fontSize: 12.5, color: palette.textMuted, marginTop: 6, maxWidth: 420, margin: "6px auto 0" }}>{hint}</div>}
      {children && <div style={{ marginTop: 18 }}>{children}</div>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="card" style={{ borderColor: "rgba(239,68,68,0.4)", background: "rgba(69,10,10,0.25)" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
        <span style={{ color: palette.danger, fontSize: 15 }}>⚠</span>
        <div>
          <div style={{ color: palette.danger, fontSize: 13, fontWeight: 600 }}>Request failed</div>
          <div className="mono" style={{ fontSize: 12, color: "#fecaca", marginTop: 4, whiteSpace: "pre-wrap" }}>{message}</div>
        </div>
      </div>
    </div>
  );
}

export function PageLoader({ label = "Fetching data…" }: { label?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: 70 }}>
      <span className="loading-spinner" style={{ width: 30, height: 30 }} />
      <span style={{ fontSize: 12.5, color: palette.textDim }}>{label}</span>
    </div>
  );
}