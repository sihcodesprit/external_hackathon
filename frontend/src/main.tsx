import { StrictMode } from "react";
import { BrowserRouter } from "react-router-dom";
import { createRoot } from "react-dom/client";
import { AnalysisProvider } from "./store/analysisContext";
import App from "./App";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AnalysisProvider>
        <App />
      </AnalysisProvider>
    </BrowserRouter>
  </StrictMode>,
);