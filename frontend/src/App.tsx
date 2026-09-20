import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { PageLoader } from "./components/ui/displays";

const CommandCenter = lazy(() => import("./pages/CommandCenter"));
const AnalysisPage = lazy(() => import("./pages/AnalysisPage"));
const ValidationPage = lazy(() => import("./pages/ValidationPage"));
const OperationsPage = lazy(() => import("./pages/OperationsPage"));

export default function App() {
  return (
    <Suspense fallback={<PageLoader label="Booting console…" />}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/validate" element={<ValidationPage />} />
          <Route path="/ops" element={<OperationsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}