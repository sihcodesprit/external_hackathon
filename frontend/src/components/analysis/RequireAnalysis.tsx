import type { ReactNode } from "react";
import { palette } from "../../styles/theme";
import { useAnalysis } from "../../store/analysisContext";
import { JobProgress } from "./JobProgress";
import { EmptyState, ErrorState, PageLoader } from "../ui/displays";
import type { AnalysisDoc } from "../../types";

export function RequireAnalysis({
  children,
  hint = "Load a PCAP, CSV or JSONL capture — or run a synthetic scenario — to generate live analysis using the Cyber World Model engine.",
  action,
}: {
  children: ReactNode | ((doc: AnalysisDoc) => ReactNode);
  hint?: string;
  action?: ReactNode;
}) {
  const { doc, job, analyzing, running, status, error, refresh } = useAnalysis();

  if (running || analyzing) {
    return (
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        <JobProgress job={job} />
      </div>
    );
  }

  if (status === "error") {
    return <ErrorState message={error ?? "Could not load the active analysis."} />;
  }

  if (status === "loading" && !doc) {
    return <PageLoader label="Loading analysis…" />;
  }

  if (!doc) {
    return (
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        <EmptyState title="No analysis loaded" hint={hint}>
          {action}
        </EmptyState>
      </div>
    );
  }

  if (typeof children === "function") {
    return <>{children(doc)}</>;
  }
  return <>{children}</>;
}

export function SectionLabel({ children, tone }: { children: ReactNode; tone?: "accent" }) {
  return (
    <div
      style={{
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: 1.2,
        textTransform: "uppercase",
        color: tone === "accent" ? palette.accent : palette.textDim,
        marginBottom: 12,
      }}
    >
      {children}
    </div>
  );
}