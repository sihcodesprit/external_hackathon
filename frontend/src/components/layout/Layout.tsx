import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { palette } from "../../styles/theme";

export function Layout() {
  return (
    <div style={{ display: "flex", minHeight: "100dvh" }}>
      <Sidebar />
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <TopBar />
        <main style={{ flex: 1, padding: 22, maxWidth: 1500, width: "100%", margin: "0 auto" }}>
          <Outlet />
        </main>
        <footer
          style={{
            padding: "10px 22px",
            fontSize: 10.5,
            color: palette.textMuted,
            borderTop: `1px solid ${palette.borderSoft}`,
          }}
        >
          Cyber World Model · AI-based Network Attack Forecasting from Network Traffic Data · Synthetic
          scenario traces are labeled SYNTHETIC and are never presented as live captures.
        </footer>
      </div>
    </div>
  );
}