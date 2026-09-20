import { TabBar, useTab } from "../components/ui/Tabs";
import Overview from "./Overview";
import AnalyzePCAP from "./AnalyzePCAP";
import Scenarios from "./Scenarios";
import LiveMonitor from "./LiveMonitor";
import UrlMonitor from "./UrlMonitor";

const mainTabs = [
  { id: "overview", label: "Overview", icon: "◈" },
  { id: "capture", label: "Capture inputs", icon: "⤒" },
];

const sourceTabs = [
  { id: "file", label: "File / PCAP", icon: "▤" },
  { id: "scenario", label: "Scenario", icon: "❖" },
  { id: "live", label: "Live capture", icon: "◉" },
  { id: "url", label: "URL monitor", icon: "⇱" },
];

export default function CommandCenter() {
  const [active, setTab] = useTab(["overview", "capture"], "overview");
  return (
    <div>
      <TabBar items={mainTabs} active={active} onSelect={setTab} />
      {active === "overview" && <Overview bare />}
      {active === "capture" && <CaptureTabs />}
    </div>
  );
}

function CaptureTabs() {
  const [src, setSrc] = useTab(["file", "scenario", "live", "url"], "file", "src");
  return (
    <div>
      <TabBar items={sourceTabs} active={src} onSelect={setSrc} />
      {src === "file" && <AnalyzePCAP bare />}
      {src === "scenario" && <Scenarios bare />}
      {src === "live" && <LiveMonitor bare />}
      {src === "url" && <UrlMonitor bare />}
    </div>
  );
}