import { useSearchParams } from "react-router-dom";
import { TabBar, useTab } from "../components/ui/Tabs";
import ModelTestCenter from "./ModelTestCenter";
import ModelTestRun from "./ModelTestRun";
import Evaluation from "./Evaluation";

const tabs = [
  { id: "model-test", label: "Model Test", icon: "▦" },
  { id: "model-run", label: "Run detail", icon: "⇉" },
  { id: "evaluation", label: "Evaluation", icon: "≈" },
];

export default function ValidationPage() {
  const [active, setTab] = useTab(["model-test", "model-run", "evaluation"], "model-test");
  const [params] = useSearchParams();
  const jobId = params.get("job") ?? "";
  return (
    <div>
      <TabBar items={tabs} active={active} onSelect={setTab} />
      {active === "model-test" && <ModelTestCenter bare />}
      {active === "model-run" && <ModelTestRun bare jobId={jobId} />}
      {active === "evaluation" && <Evaluation bare />}
    </div>
  );
}