import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "../services/api";
import type { AnalysisDoc, JobPoll } from "../types";

export type AnalysisStatus = "loading" | "idle" | "ready" | "error";

interface AnalysisState {
  doc: AnalysisDoc | null;
  job: JobPoll | null;
  running: boolean;
  analyzing: boolean;
  sourceLabel: string | null;
  analysisId: string | null;
  status: AnalysisStatus;
  error: string | null;
  /** Refetch the canonical active analysis from the backend (source of truth). */
  refresh: () => Promise<void>;
  /** Adopt a completed analysis (by id + document) as the active analysis. */
  activateAnalysis: (analysisId: string, doc: AnalysisDoc) => void;
  /** Adopt a just-completed analysis job (e.g. Model Test Center Run All). */
  adoptCompletedJob: (jobId: string) => Promise<void>;
  startAnalysis: (file: File, member?: string) => Promise<void>;
  startScenario: (scenarioId: string) => Promise<void>;
  clear: () => void;
  setDoc: (doc: AnalysisDoc | null) => void;
}

const STORAGE_KEY = "netwatch_active_analysis_id";
const Ctx = createContext<AnalysisState | null>(null);

function persistActiveId(id: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable — backend remains the source of truth */
  }
}

function readPersistedId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** A 404 from the canonical-analysis endpoints means "nothing to show yet"
 * (no active analysis / server restarted), not a hard failure. */
function isNotFound(e: unknown): boolean {
  return (e instanceof Error && (e as Error & { status?: number }).status === 404) || false;
}

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [doc, setDocRaw] = useState<AnalysisDoc | null>(null);
  const [job, setJob] = useState<JobPoll | null>(null);
  const [running, setRunning] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [sourceLabel, setSourceLabel] = useState<string | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<number | undefined>(undefined);
  const hydrated = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      window.clearTimeout(pollTimer.current);
      pollTimer.current = undefined;
    }
  }, []);

  const activateAnalysis = useCallback((id: string, d: AnalysisDoc) => {
    setDocRaw(d);
    setAnalysisId(id);
    persistActiveId(id);
    setSourceLabel(d.member ?? d.filename);
    setStatus("ready");
    setError(null);
  }, []);

  const clear = useCallback(() => {
    stopPolling();
    setDocRaw(null);
    setJob(null);
    setRunning(false);
    setAnalyzing(false);
    setSourceLabel(null);
    setAnalysisId(null);
    persistActiveId(null);
    setStatus("idle");
    setError(null);
  }, [stopPolling]);

  /** Persist a freshly completed analysis job (upload or scenario). */
  const startJob = useCallback(
    async (jobId: string, source: string) => {
      setRunning(true);
      setAnalyzing(true);
      setError(null);
      setSourceLabel(source);
      const poll = async () => {
        try {
          const p = await api.pollJob(jobId);
          setJob(p);
          if (p.status === "done") {
            if (p.result?.status === "ok") {
              const id = p.result.analysis_id ?? jobId;
              activateAnalysis(id, p.result);
            }
            setRunning(false);
            setAnalyzing(false);
            return;
          }
          if (p.status === "error") {
            setRunning(false);
            setAnalyzing(false);
            setError(p.error ?? "Analysis failed.");
            return;
          }
          pollTimer.current = window.setTimeout(poll, 750);
        } catch {
          pollTimer.current = window.setTimeout(poll, 1500);
        }
      };
      poll();
    },
    [activateAnalysis],
  );

  const startAnalysis = useCallback(
    async (file: File, member?: string) => {
      stopPolling();
      setDocRaw(null);
      setJob(null);
      const { job_id } = await api.analyze(file, member);
      await startJob(job_id, member ?? file.name);
    },
    [startJob, stopPolling],
  );

  const startScenario = useCallback(
    async (scenarioId: string) => {
      stopPolling();
      setDocRaw(null);
      setJob(null);
      const { job_id } = await api.runScenario(scenarioId);
      await startJob(job_id, `scenario:${scenarioId}`);
    },
    [startJob, stopPolling],
  );

  const refresh = useCallback(async () => {
    setStatus("loading");
    try {
      const active = await api.activeAnalysis();
      if (active.analysis_id && active.doc) {
        activateAnalysis(active.analysis_id, active.doc);
      } else {
        setDocRaw(null);
        setAnalysisId(null);
        persistActiveId(null);
        setStatus("idle");
      }
    } catch (e) {
      if (isNotFound(e)) {
        setDocRaw(null);
        setAnalysisId(null);
        persistActiveId(null);
        setError(null);
        setStatus("idle");
        return;
      }
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  }, [activateAnalysis]);

  /** Adopt a completed job's canonical analysis (Model Test Center Run All). */
  const adoptCompletedJob = useCallback(
    async (jobId: string) => {
      try {
        const d = await api.analysis(jobId);
        if (d?.status === "ok") {
          activateAnalysis(d.analysis_id ?? jobId, d);
          return;
        }
        await refresh();
      } catch {
        // The job id may not exist as an analysis yet — fall back to the
        // backend's currently active analysis.
        await refresh();
      }
    },
    [activateAnalysis, refresh],
  );

  /** Restore the active analysis after navigation, refresh or direct URL load. */
  const hydrate = useCallback(async () => {
    setStatus("loading");
    const saved = readPersistedId();
    if (saved) {
      try {
        const d = await api.analysis(saved);
        activateAnalysis(d.analysis_id ?? saved, d);
        return;
      } catch {
        persistActiveId(null); // stale id — fall through to server active
      }
    }
    try {
      const active = await api.activeAnalysis();
      if (active.analysis_id && active.doc) {
        activateAnalysis(active.analysis_id, active.doc);
      } else {
        setStatus("idle");
      }
    } catch (e) {
      if (isNotFound(e)) {
        setStatus("idle");
        setError(null);
        return;
      }
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  }, [activateAnalysis]);

  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    void hydrate();
  }, [hydrate]);

  const setDoc = useCallback((d: AnalysisDoc | null) => {
    setDocRaw(d);
    if (!d) {
      setAnalysisId(null);
      persistActiveId(null);
      setStatus("idle");
    }
  }, []);

  const value = useMemo<AnalysisState>(
    () => ({
      doc,
      job,
      running,
      analyzing,
      sourceLabel,
      analysisId,
      status,
      error,
      refresh,
      activateAnalysis,
      adoptCompletedJob,
      startAnalysis,
      startScenario,
      clear,
      setDoc,
    }),
    [
      doc,
      job,
      running,
      analyzing,
      sourceLabel,
      analysisId,
      status,
      error,
      refresh,
      activateAnalysis,
      adoptCompletedJob,
      startAnalysis,
      startScenario,
      clear,
      setDoc,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAnalysis(): AnalysisState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAnalysis must be used within AnalysisProvider");
  return ctx;
}