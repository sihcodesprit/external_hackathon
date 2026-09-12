import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "../services/api";
import type { AnalysisDoc, JobPoll } from "../types";

interface AnalysisState {
  doc: AnalysisDoc | null;
  job: JobPoll | null;
  running: boolean;
  analyzing: boolean;
  sourceLabel: string | null;
  startAnalysis: (file: File, member?: string) => Promise<void>;
  startScenario: (scenarioId: string) => Promise<void>;
  clear: () => void;
  setDoc: (doc: AnalysisDoc | null) => void;
}

const Ctx = createContext<AnalysisState | null>(null);

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [doc, setDoc] = useState<AnalysisDoc | null>(null);
  const [job, setJob] = useState<JobPoll | null>(null);
  const [running, setRunning] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [sourceLabel, setSourceLabel] = useState<string | null>(null);
  const pollTimer = useRef<number | undefined>(undefined);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      window.clearTimeout(pollTimer.current);
      pollTimer.current = undefined;
    }
  }, []);

  const clear = useCallback(() => {
    stopPolling();
    setDoc(null);
    setJob(null);
    setRunning(false);
    setAnalyzing(false);
    setSourceLabel(null);
  }, [stopPolling]);

  const startJob = useCallback(
    async (jobId: string, source: string) => {
      setRunning(true);
      setAnalyzing(true);
      setSourceLabel(source);
      const poll = async () => {
        try {
          const p = await api.pollJob(jobId);
          setJob(p);
          if (p.status === "done") {
            if (p.result?.status === "ok") setDoc(p.result);
            setRunning(false);
            setAnalyzing(false);
            return;
          }
          if (p.status === "error") {
            setRunning(false);
            setAnalyzing(false);
            return;
          }
          pollTimer.current = window.setTimeout(poll, 750);
        } catch {
          pollTimer.current = window.setTimeout(poll, 1500);
        }
      };
      poll();
    },
    [],
  );

  const startAnalysis = useCallback(
    async (file: File, member?: string) => {
      stopPolling();
      setDoc(null);
      setJob(null);
      const { job_id } = await api.analyze(file, member);
      await startJob(job_id, member ?? file.name);
    },
    [startJob, stopPolling],
  );

  const startScenario = useCallback(
    async (scenarioId: string) => {
      stopPolling();
      setDoc(null);
      setJob(null);
      const { job_id } = await api.runScenario(scenarioId);
      await startJob(job_id, `scenario:${scenarioId}`);
    },
    [startJob, stopPolling],
  );

  const value = useMemo<AnalysisState>(
    () => ({
      doc,
      job,
      running,
      analyzing,
      sourceLabel,
      startAnalysis,
      startScenario,
      clear,
      setDoc,
    }),
    [doc, job, running, analyzing, sourceLabel, startAnalysis, startScenario, clear],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAnalysis(): AnalysisState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAnalysis must be used within AnalysisProvider");
  return ctx;
}