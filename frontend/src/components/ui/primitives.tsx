import type { ReactNode } from "react";
import { palette, radius } from "../../styles/theme";

export function Box({
  children,
  ...style
}: { children?: ReactNode } & React.CSSProperties) {
  return <div style={style}>{children}</div>;
}

interface CardProps {
  children: ReactNode;
  title?: string;
  subtitle?: ReactNode;
  headerRight?: ReactNode;
  bodyStyle?: React.CSSProperties;
  style?: React.CSSProperties;
  glow?: boolean;
  pad?: boolean;
}

export function Card({ children, title, subtitle, headerRight, bodyStyle, style, glow, pad = true }: CardProps) {
  return (
    <div className={`card${glow ? " glow" : ""}`} style={style}>
      {(title || headerRight) && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 12,
            marginBottom: 14,
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: 0.2, color: palette.text }}>
              {title}
            </div>
            {subtitle && (
              <div style={{ fontSize: 11.5, color: palette.textDim, marginTop: 2 }}>{subtitle}</div>
            )}
          </div>
          {headerRight && <div>{headerRight}</div>}
        </div>
      )}
      <div style={{ ...(pad ? {} : {}), ...bodyStyle }}>{children}</div>
    </div>
  );
}

export function Grid({ children, cols = "auto", gap = 14, style }: {
  children: ReactNode;
  cols?: string;
  gap?: number;
  style?: React.CSSProperties;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: cols, gap, ...style }}>{children}</div>
  );
}

export function Spinner({ size = 24, color = palette.accent }: { size?: number; color?: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        border: `2px solid ${palette.border}`,
        borderTopColor: color,
        borderRadius: "50%",
        animation: "spin 800ms linear infinite",
      }}
    />
  );
}

export function Pill({ tone = "default", children }: { tone?: "default" | "accent" | "good" | "warn" | "danger" | "info"; children: ReactNode }) {
  const colors: Record<string, string> = {
    default: "#8b98c2",
    accent: "#22d3ee",
    good: "#34d399",
    warn: "#fbbf24",
    danger: "#ef4444",
    info: "#38bdf8",
  };
  const c = colors[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "1px 9px",
        borderRadius: radius.pill,
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: 0.4,
        textTransform: "uppercase",
        color: c,
        background: `${c}14`,
        border: `1px solid ${c}38`,
      }}
    >
      {children}
    </span>
  );
}

export function Dot({ color, size = 7 }: { color: string; size?: number }) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        boxShadow: `0 0 8px ${color}80`,
        display: "inline-block",
        flexShrink: 0,
      }}
    />
  );
}

export function ThreatText({ level }: { level: string }) {
  const map: Record<string, { color: string; short: string }> = {
    BENIGN: { color: "#38bdf8", short: "Benign" },
    LOW: { color: "#34d399", short: "Low" },
    GUARDED: { color: "#4ade80", short: "Low" },
    MEDIUM: { color: "#fbbf24", short: "Medium" },
    ELEVATED: { color: "#fbbf24", short: "Elevated" },
    HIGH: { color: "#fb923c", short: "High" },
    CRITICAL: { color: "#ef4444", short: "Critical" },
  };
  const m = map[level] ?? map.BENIGN;
  return (
    <span
      style={{
        color: m.color,
        fontWeight: 650,
        letterSpacing: 0.6,
        fontSize: 12,
        textTransform: "uppercase",
      }}
    >
      {m.short}
    </span>
  );
}

export function Tag({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: radius.sm,
        fontSize: 11,
        fontWeight: 500,
        color,
        background: `${color}14`,
        border: `1px solid ${color}30`,
      }}
    >
      {children}
    </span>
  );
}

export function Divider({ label }: { label?: string }) {
  return (
    <div
      style={{
        height: 1,
        background: palette.borderSoft,
        margin: "18px 0",
        position: "relative",
      }}
    >
      {label && (
        <span
          style={{
            position: "absolute",
            top: -9,
            left: 10,
            padding: "0 8px",
            background: "#0d1425",
            fontSize: 10,
            letterSpacing: 1.5,
            color: palette.textMuted,
            textTransform: "uppercase",
          }}
        >
          {label}
        </span>
      )}
    </div>
  );
}

export function Labeled({ label, children, width = 130 }: { label: string; children: ReactNode; width?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ width, flexShrink: 0, fontSize: 11.5, color: palette.textDim }}>{label}</span>
      <span style={{ fontSize: 12.5 }}>{children}</span>
    </div>
  );
}

export function Bar({
  value,
  max = 100,
  color,
  height = 6,
  background = palette.border,
}: {
  value: number;
  max?: number;
  color?: string;
  height?: number;
  background?: string;
}) {
  const w = Math.max(0, Math.min(100, (value / Math.max(1, max)) * 100));
  return (
    <div style={{ height, background, borderRadius: radius.pill, overflow: "hidden", width: "100%" }}>
      <div style={{ height: "100%", width: `${w}%`, background: color ?? palette.accent, borderRadius: radius.pill }} />
    </div>
  );
}

export function KeyValue({ k, v, mono }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "5px 0", borderBottom: `1px solid ${palette.borderSoft}` }}>
      <span style={{ fontSize: 12, color: palette.textDim }}>{k}</span>
      <span className={mono ? "mono" : ""} style={{ fontSize: 12.5, color: palette.text, textAlign: "right" }}>
        {v}
      </span>
    </div>
  );
}