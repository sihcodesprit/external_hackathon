import { TabBar, useTab } from "../components/ui/Tabs";
import NetworkState from "./NetworkState";
import Forecast from "./Forecast";
import AttackGraph from "./AttackGraph";
import Mitre from "./Mitre";
import Explainability from "./Explainability";

const tabs = [
  { id: "network-state", label: "Network State", icon: "◉" },
  { id: "forecast", label: "Forecast", icon: "⇉" },
  { id: "attack-graph", label: "Attack Graph", icon: "⛨" },
  { id: "mitre", label: "MITRE", icon: "⛊" },
  { id: "explainability", label: "Why", icon: "⊕" },
];

export default function AnalysisPage() {
  const [active, setTab] = useTab(
    ["network-state", "forecast", "attack-graph", "mitre", "explainability"],
    "forecast",
  );
  return (
    <div>
      <TabBar items={tabs} active={active} onSelect={setTab} />
      {active === "network-state" && <NetworkState bare />}
      {active === "forecast" && <Forecast bare />}
      {active === "attack-graph" && <AttackGraph bare />}
      {active === "mitre" && <Mitre bare />}
      {active === "explainability" && <Explainability bare />}
    </div>
  );
}