import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { PageLoader } from "./components/ui/displays";

const Overview = lazy(() => import("./pages/Overview"));
const AnalyzePCAP = lazy(() => import("./pages/AnalyzePCAP"));
const LiveMonitor = lazy(() => import("./pages/LiveMonitor"));
const NetworkState = lazy(() => import("./pages/NetworkState"));
const Forecast = lazy(() => import("./pages/Forecast"));
const AttackGraph = lazy(() => import("./pages/AttackGraph"));
const Mitre = lazy(() => import("./pages/Mitre"));
const Explainability = lazy(() => import("./pages/Explainability"));
const CounterfactualLab = lazy(() => import("./pages/CounterfactualLab"));
const ModelTestCenter = lazy(() => import("./pages/ModelTestCenter"));
const ModelTestRun = lazy(() => import("./pages/ModelTestRun"));
const Evaluation = lazy(() => import("./pages/Evaluation"));
const Scenarios = lazy(() => import("./pages/Scenarios"));
const History = lazy(() => import("./pages/History"));
const ReportExport = lazy(() => import("./pages/ReportExport"));
const System = lazy(() => import("./pages/System"));

export default function App() {
  return (
    <Suspense fallback={<PageLoader label="Booting console…" />}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Overview />} />
          <Route path="/analyze" element={<AnalyzePCAP />} />
          <Route path="/live" element={<LiveMonitor />} />
          <Route path="/network" element={<NetworkState />} />
          <Route path="/forecast" element={<Forecast />} />
          <Route path="/attack-graph" element={<AttackGraph />} />
          <Route path="/mitre" element={<Mitre />} />
          <Route path="/explainability" element={<Explainability />} />
          <Route path="/counterfactual" element={<CounterfactualLab />} />
          <Route path="/model-test" element={<ModelTestCenter />} />
          <Route path="/model-test/run/:jobId" element={<ModelTestRun />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/scenarios" element={<Scenarios />} />
          <Route path="/history" element={<History />} />
          <Route path="/report" element={<ReportExport />} />
          <Route path="/system" element={<System />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}