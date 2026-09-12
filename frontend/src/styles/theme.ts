export const palette = {
  bg: "#050810",
  bgRaised: "#0a0f1e",
  bgElevated: "#0e1526",
  panel: "rgba(16, 24, 42, 0.72)",
  panelSolid: "#0d1425",
  panelHover: "#131c33",
  border: "#1d2a45",
  borderSoft: "#16203a",
  text: "#dbe4ff",
  textDim: "#8b98c2",
  textMuted: "#5a6788",
  accent: "#22d3ee",
  accentSoft: "rgba(34, 211, 238, 0.10)",
  accentBorder: "rgba(34, 211, 238, 0.35)",
  accent2: "#8b5cf6",
  accent2Soft: "rgba(139, 92, 246, 0.12)",
  good: "#34d399",
  warn: "#fbbf24",
  danger: "#f87171",
  critical: "#ef4444",
  chartGrid: "#182440",
  mono: "ui-monospace, 'Cascadia Code', 'Segoe UI Mono', Consolas, monospace",
};

export const danger = {
  LOW: "#34d399",
  GUARDED: "#4ade80",
  ELEVATED: "#fbbf24",
  HIGH: "#fb923c",
  CRITICAL: "#ef4444",
  MEDIUM: "#e2b714",
  BENIGN: "#34d399",
};

export const severityOrder = ["LOW", "GUARDED", "ELEVATED", "HIGH", "CRITICAL"];

export const severityIndex = (s: string): number => {
  const i = severityOrder.indexOf(s.toUpperCase());
  return i < 0 ? 0 : i;
};

export const threatGaugeColor = (level: string): string => {
  switch (level.toUpperCase()) {
    case "CRITICAL":
      return "#ef4444";
    case "HIGH":
      return "#fb923c";
    case "MEDIUM":
    case "ELEVATED":
    case "GUARDED":
      return "#fbbf24";
    case "LOW":
      return "#34d399";
    default:
    case "BENIGN":
      return "#38bdf8";
  }
};

export const stageColors: Record<string, string> = {
  Benign: "#34d399",
  Reconnaissance: "#38bdf8",
  Discovery: "#38bdf8",
  "Initial Access": "#fbbf24",
  Execution: "#fb923c",
  "Lateral Movement": "#c084fc",
  "Command and Control": "#e879f9",
  "Command & Control": "#e879f9",
  "Command &amp; Control": "#e879f9",
  Exfiltration: "#ef4444",
};

export const stageColor = (stage: string): string =>
  stageColors[stage] ?? "#8b98c2";

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const radius = {
  sm: 6,
  md: 10,
  lg: 14,
  pill: 999,
};

export const fontStack =
  "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif";

export const shadows = {
  card: "0 6px 24px rgba(0,0,0,0.35)",
  glow: `0 0 0 1px rgba(34,211,238,0.25), 0 0 24px rgba(34,211,238,0.08)`,
};

export const motion = {
  fast: "120ms ease",
  base: "200ms ease",
};

export const breakpoints = {
  md: 900,
  lg: 1200,
};