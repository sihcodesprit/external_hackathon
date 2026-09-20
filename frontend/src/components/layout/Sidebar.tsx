import { NavLink, useLocation } from "react-router-dom";
import { palette, motion } from "../../styles/theme";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  default?: string;
  tabs: Array<{ id: string; label: string }>;
}

const nav: NavItem[] = [
  {
    to: "/",
    label: "Dashboard",
    icon: "◈",
    default: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "capture", label: "Capture" },
    ],
  },
  {
    to: "/analysis",
    label: "Analysis",
    icon: "⇉",
    default: "forecast",
    tabs: [
      { id: "network-state", label: "Network State" },
      { id: "forecast", label: "Forecast" },
      { id: "attack-graph", label: "Attack Graph" },
      { id: "mitre", label: "MITRE" },
      { id: "explainability", label: "Why" },
    ],
  },
  {
    to: "/validate",
    label: "Validation",
    icon: "▦",
    default: "model-test",
    tabs: [
      { id: "model-test", label: "Model Test" },
      { id: "model-run", label: "Run Detail" },
      { id: "evaluation", label: "Evaluation" },
    ],
  },
  {
    to: "/ops",
    label: "Operations",
    icon: "⚙",
    default: "history",
    tabs: [
      { id: "history", label: "History" },
      { id: "report", label: "Report" },
      { id: "system", label: "System" },
    ],
  },
];

export function Sidebar() {
  const location = useLocation();
  return (
    <aside
      style={{
        width: 218,
        flexShrink: 0,
        height: "100dvh",
        position: "sticky",
        top: 0,
        display: "flex",
        flexDirection: "column",
        background: `linear-gradient(180deg, ${palette.bgRaised} 0%, #070b16 100%)`,
        borderRight: `1px solid ${palette.borderSoft}`,
        zIndex: 40,
      }}
    >
      <nav style={{ flex: 1, overflowY: "auto", padding: "10px 8px", display: "flex", flexDirection: "column", gap: 4 }}>
        {nav.map((item) => {
          const isActive =
            item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
          return (
            <div key={item.to} style={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive: a }) => (a ? "active" : "")}
                style={({ isActive: a }) => ({
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 10px",
                  borderRadius: 8,
                  fontSize: 12.5,
                  color: a ? palette.accent : palette.textDim,
                  background: a ? palette.accentSoft : "transparent",
                  borderLeft: `2px solid ${a ? palette.accent : "transparent"}`,
                  transition: `background ${motion.fast}, color ${motion.fast}`,
                })}
              >
                <span style={{ width: 16, textAlign: "center", fontSize: 13, opacity: isActive ? 1 : 0.7 }}>
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
              {isActive && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, padding: "4px 8px 6px 28px" }}>
                  {item.tabs.map((t) => {
                    const tabActive =
                      new URLSearchParams(location.search).get("tab") === t.id ||
                      (!location.search.includes("tab=") && t.id === (item.default ?? item.tabs[0].id));
                    return (
                      <NavLink
                        key={t.id}
                        to={`${item.to}?tab=${t.id}`}
                        style={{
                          fontSize: 10.5,
                          padding: "2px 8px",
                          borderRadius: 6,
                          color: tabActive ? palette.accent : palette.textMuted,
                          background: tabActive ? `${palette.accent}18` : "transparent",
                          border: `1px solid ${tabActive ? palette.accentBorder : "transparent"}`,
                          textDecoration: "none",
                        }}
                      >
                        {t.label}
                      </NavLink>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div style={{ padding: "12px 16px", borderTop: `1px solid ${palette.borderSoft}`, fontSize: 10, color: palette.textMuted, letterSpacing: 0.4 }}>
        NetWatch · LSTM World Model
      </div>
    </aside>
  );
}