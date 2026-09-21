import { useEffect, useState } from "react";
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
      { id: "lab", label: "Attack Lab" },
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

const isTabActive = (
  location: ReturnType<typeof useLocation>,
  item: NavItem,
  id: string,
): boolean => {
  const ts = new URLSearchParams(location.search).get("tab");
  return (ts ?? item.default ?? item.tabs[0].id) === id;
};

export function Sidebar() {
  const location = useLocation();
  const active =
    nav.find((item) =>
      item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to),
    )?.to ?? nav[0].to;
  const [openTo, setOpenTo] = useState<string | null>(active);

  useEffect(() => {
    setOpenTo(active);
  }, [active]);

  const toggle = (to: string) => setOpenTo((prev) => (prev === to ? null : to));

  return (
    <aside
      style={{
        width: 224,
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
      <div
        style={{
          padding: "14px 16px 12px",
          borderBottom: `1px solid ${palette.borderSoft}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              width: 26,
              height: 26,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 7,
              fontSize: 15,
              background: `${palette.accent}1a`,
              color: palette.accent,
              border: `1px solid ${palette.accentBorder}`,
            }}
          >
            ◈
          </span>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 700, letterSpacing: 0.3, color: palette.text, lineHeight: 1.2 }}>
              NetWatch
            </div>
            <div style={{ fontSize: 8.5, letterSpacing: 1.1, color: palette.textMuted, marginTop: 2 }}>
              CYBER WORLD MODEL
            </div>
          </div>
        </div>
      </div>

      <nav
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          padding: "10px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        {nav.map((item) => {
          const isActive = item.to === active;
          const isOpen = openTo === item.to;
          return (
            <div
              key={item.to}
              style={{
                borderRadius: 9,
                background: isActive ? `${palette.accentSoft}0d` : "transparent",
                border: `1px solid ${isActive ? "rgba(34,211,238,0.28)" : "transparent"}`,
                overflow: "hidden",
              }}
            >
              <NavLink
                to={item.to}
                end={item.to === "/"}
                onClick={() => toggle(item.to)}
                style={({ isActive: a }) => ({
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  padding: "8px 11px",
                  fontSize: 12.5,
                  fontWeight: a ? 700 : 550,
                  color: a ? palette.text : palette.textDim,
                  textDecoration: "none",
                  transition: `color ${motion.fast}`,
                })}
              >
                <span style={{ width: 16, textAlign: "center", fontSize: 13, opacity: isActive ? 1 : 0.7 }}>
                  {item.icon}
                </span>
                {item.label}
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 8.5,
                    fontWeight: 600,
                    opacity: 1,
                    color: isActive ? palette.accent : palette.textMuted,
                    transition: "transform 120ms ease",
                    transform: isOpen ? "rotate(90deg)" : "none",
                  }}
                >
                  ▸
                </span>
              </NavLink>

              {isOpen && (
                <div
                  className="nav-sub-list"
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 1,
                    padding: "0 6px 7px",
                    borderTop: `1px solid ${isActive ? "rgba(34,211,238,0.12)" : palette.borderSoft}`,
                    marginTop: 2,
                    paddingTop: 6,
                  }}
                >
                  {item.tabs.map((t) => {
                    const tabActive = isTabActive(location, item, t.id);
                    return (
                      <NavLink
                        key={t.id}
                        to={`${item.to}?tab=${t.id}`}
                        className="nav-sub-link"
                        style={() => ({
                          display: "flex",
                          alignItems: "center",
                          gap: 7,
                          padding: "5px 8px 5px 12px",
                          borderRadius: 6,
                          fontSize: 11.5,
                          color: tabActive ? palette.accent : palette.textMuted,
                          background: tabActive ? `${palette.accent}14` : "transparent",
                          borderLeft: `2px solid ${tabActive ? palette.accent : "transparent"}`,
                          transition: `background ${motion.fast}, color ${motion.fast}`,
                        })}
                      >
                        <span style={{ fontSize: 8, opacity: tabActive ? 1 : 0.5 }}>●</span>
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

      <div
        style={{
          padding: "10px 16px",
          borderTop: `1px solid ${palette.borderSoft}`,
          fontSize: 9.5,
          color: palette.textMuted,
          letterSpacing: 0.4,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: palette.good }} />
        NetWatch · LSTM World Model
      </div>
    </aside>
  );
}