import type { ReactNode } from "react";
import { palette } from "../../styles/theme";
import { useAnalysis } from "../../store/analysisContext";
import { JobProgress } from "./JobProgress";
import { EmptyState } from "../ui/displays";

export function RequireAnalysis({
  children,
  hint = "Load a PCAP, CSV or JSONL capture — or run a synthetic scenario — to generate live analysis using the Cyber World Model engine.",
  action,
}: {
  children: ReactNode;
  hint?: string;
  action?: ReactNode;
}) {
  const { doc, job, analyzing, running } = useAnalysis();

  if (!doc) {
    if (running || analyzing) {
      return (
        <div style={{ maxWidth: 560, margin: "0 auto" }}>
          <JobProgress job={job} />
        </div>
      );
    }
    return (
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        <EmptyState title="No analysis loaded" hint={hint}>
          {action}
        </EmptyState>
      </div>
    );
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