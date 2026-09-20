import { TabBar, useTab } from "../components/ui/Tabs";
import Overview from "./Overview";
import AnalyzePCAP from "./AnalyzePCAP";
import Scenarios from "./Scenarios";
import LiveMonitor from "./LiveMonitor";
import UrlMonitor from "./UrlMonitor";
import AttackLab from "./AttackLab";

const mainTabs = [
  { id: "overview", label: "Overview", icon: "◈" },
  { id: "lab", label: "Attack Lab", icon: "⚡" },
  { id: "capture", label: "Capture inputs", icon: "⤒" },
];

const sourceTabs = [
  { id: "file", label: "File / PCAP", icon: "▤" },
  { id: "lab", label: "Attack Lab", icon: "⚡" },
  { id: "scenario", label: "Scenario", icon: "❖" },
  { id: "live", label: "Live capture", icon: "◉" },
  { id: "url", label: "URL monitor", icon: "⇱" },
];

export default function CommandCenter() {
  const [active, setTab] = useTab(["overview", "lab", "capture"], "overview");
  return (
    <div>
      <TabBar items={mainTabs} active={active} onSelect={setTab} />
      {active === "overview" && <Overview bare />}
      {active === "lab" && <AttackLab bare />}
      {active === "capture" && <CaptureTabs />}
    </div>
  );
}

function CaptureTabs() {
  const [src, setSrc] = useTab(["file", "lab", "scenario", "live", "url"], "file", "src");
  return (
    <div>
      <TabBar items={sourceTabs} active={src} onSelect={setSrc} />
      {src === "file" && <AnalyzePCAP bare />}
      {src === "lab" && <AttackLab bare />}
      {src === "scenario" && <Scenarios bare />}
      {src === "live" && <LiveMonitor bare />}
      {src === "url" && <UrlMonitor bare />}
    </div>
  );
}