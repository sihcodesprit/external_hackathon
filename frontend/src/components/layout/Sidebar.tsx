import { NavLink } from "react-router-dom";
import { palette, motion } from "../../styles/theme";

const nav = [
  { to: "/", label: "Overview", icon: "◈" },
  { to: "/analyze", label: "Analyze PCAP", icon: "⤒" },
  { to: "/live", label: "Live Monitor", icon: "◉" },
  { to: "/network", label: "Network State", icon: "◉" },
  { to: "/forecast", label: "Forecast & Projection", icon: "⇉" },
  { to: "/attack-graph", label: "Attack Graph", icon: "⛨" },
  { to: "/mitre", label: "MITRE Trajectory", icon: "⛊" },
  { to: "/explainability", label: "Explainability", icon: "⊕" },
  { to: "/counterfactual", label: "Counterfactual Lab", icon: "⇋" },
  { to: "/model-test", label: "Model Test Center", icon: "▦" },
  { to: "/evaluation", label: "Evaluation", icon: "≈" },
  { to: "/scenarios", label: "Scenarios", icon: "❖" },
  { to: "/history", label: "History", icon: "≡" },
  { to: "/report", label: "Export Report", icon: "⇓" },
  { to: "/system", label: "System", icon: "⚙" },
];

export function Sidebar() {
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
      <div style={{ padding: "18px 16px 14px", borderBottom: `1px solid ${palette.borderSoft}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              display: "grid",
              placeItems: "center",
              background: "linear-gradient(135deg, #164e63, #0f766e)",
              boxShadow: "0 0 18px rgba(34,211,238,0.35)",
              color: "#e7f7ff",
              fontSize: 15,
            }}
          >
            ⬡
          </div>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 700, color: palette.text, letterSpacing: 0.3 }}>
              CYBER WORLD
            </div>
            <div style={{ fontSize: 10, color: palette.textMuted, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Attack Forecasting Engine
            </div>
          </div>
        </div>
      </div>

      <nav style={{ flex: 1, overflowY: "auto", padding: "10px 8px", display: "flex", flexDirection: "column", gap: 1 }}>
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => (isActive ? "active" : "")}
            style={({ isActive }) => ({
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 10px",
              borderRadius: 8,
              fontSize: 12.5,
              color: isActive ? palette.accent : palette.textDim,
              background: isActive ? palette.accentSoft : "transparent",
              borderLeft: `2px solid ${isActive ? palette.accent : "transparent"}`,
              transition: `background ${motion.fast}, color ${motion.fast}`,
            })}
          >
            {({ isActive }) => (
              <>
                <span style={{ width: 16, textAlign: "center", fontSize: 13, opacity: isActive ? 1 : 0.7 }}>
                  {item.icon}
                </span>
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div style={{ padding: "12px 16px", borderTop: `1px solid ${palette.borderSoft}`, fontSize: 10, color: palette.textMuted, letterSpacing: 0.4 }}>
        NetWatch · LSTM World Model
      </div>
    </aside>
  );
}