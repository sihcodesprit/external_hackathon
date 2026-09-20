import { TabBar, useTab } from "../components/ui/Tabs";
import History from "./History";
import ReportExport from "./ReportExport";
import System from "./System";

const tabs = [
  { id: "history", label: "History", icon: "≡" },
  { id: "report", label: "Report", icon: "⇓" },
  { id: "system", label: "System", icon: "⚙" },
];

export default function OperationsPage() {
  const [active, setTab] = useTab(["history", "report", "system"], "history");
  return (
    <div>
      <TabBar items={tabs} active={active} onSelect={setTab} />
      {active === "history" && <History bare />}
      {active === "report" && <ReportExport bare />}
      {active === "system" && <System bare />}
    </div>
  );
}