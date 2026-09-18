import type {
  ActiveAnalysisInfo,
  AnalysisDoc,
  ForecastBlock,
  HistoryEntry,
  JobPoll,
  LiveAnalysisDoc,
  LiveHealthInfo,
  LiveInterface,
  LiveSessionHistory,
  LiveStartResponse,
  LiveStatusResponse,
  MitreTrajectoryStep,
  ModuleTestInfo,
  ModuleTestResult,
  ModelTestJobSummary,
  ModelTestRunJob,
  ReportDocument,
  ScenarioInfo,
  SystemInfo,
  TopologyData,
  UrlStartRequest,
  UrlStartResponse,
  UrlStatusResponse,
  ZipInspect,
} from "../types";

const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers:
      init && init.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  const ct = res.headers.get("content-type") ?? "";
  if (!res.ok) {
    const detail = ct.includes("json") ? await res.json() : {};
    const err = new Error(
      `API ${path} → ${res.status}: ${(detail as Record<string, unknown>).error ?? detail.message ?? res.statusText}`,
    ) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return ct.includes("json") ? ((await res.json()) as T) : ((await res.text()) as unknown as T);
}

export interface AnalyzeResponse {
  job_id: string;
}

export interface ScenarioRunResponse {
  job_id: string;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  systemInfo: () => request<SystemInfo>("/api/system"),

  ensemble: () => request<{ status: string }>("/api/ensemble"),

  analyze: (file: File, member?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    if (member) fd.append("member", member);
    return request<AnalyzeResponse>("/api/analyze", { method: "POST", body: fd });
  },

  pollJob: (jobId: string) => request<JobPoll>(`/api/analyze/${jobId}`),

  analysis: (analysisId: string) =>
    request<AnalysisDoc>(`/api/analysis/${encodeURIComponent(analysisId)}`),

  activeAnalysis: () => request<ActiveAnalysisInfo>("/api/analysis/active"),

  inspectZip: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ZipInspect>("/api/zip/inspect", { method: "POST", body: fd });
  },

  upload: (file: File, member?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    if (member) fd.append("member", member);
    return request<{ status: string; doc: AnalysisDoc }>("/api/upload", {
      method: "POST",
      body: fd,
    });
  },

  history: () => request<{ analyses: HistoryEntry[] }>("/api/history").then((r) => r.analyses),

  rawReport: (jobId?: string) =>
    request<ReportDocument>(`/api/report${jobId ? `/${jobId}` : ""}`),

  rawEvaluation: () =>
    request<Record<string, unknown>>("/api/evaluation").then((r) => r),

  reportDownloadUrl: (jobId?: string) =>
    `/api/report${jobId ? `/${jobId}` : ""}?download=1`,

  scenarios: () => request<{ scenarios: ScenarioInfo[] }>("/api/scenarios").then((r) => r.scenarios),

  runScenario: (scenarioId: string) =>
    request<ScenarioRunResponse>(`/api/scenario/run/${scenarioId}`, { method: "POST" }),

  testModules: () =>
    request<{ modules: ModuleTestInfo[] }>("/api/test-modules").then((r) => r.modules),

  runTestModule: (moduleId: string) =>
    request<ModuleTestResult>(`/api/test-module/${moduleId}`, { method: "POST" }),

  createModelTestJob: () =>
    request<{ job_id: string }>("/api/model-test/jobs", { method: "POST" }),

  modelTestJobs: () =>
    request<{ jobs: ModelTestJobSummary[] }>("/api/model-test/jobs").then((r) => r.jobs),

  modelTestJob: (jobId: string) => request<ModelTestRunJob>(`/api/model-test/jobs/${jobId}`),

  modelTestRetry: (jobId: string, moduleId: string) =>
    request<{ job_id: string; module: string }>(
      `/api/model-test/jobs/${jobId}/retry/${moduleId}`,
      { method: "POST" },
    ),

  modelsStatus: () => request<ModelStatus>("/api/models/status"),

  retrain: () => request<{ status: string; message: string }>("/api/retrain", { method: "POST" }),

  forecast: () => request<{ status: string; forecast: ForecastBlock }>("/api/forecast").then((r) => r.forecast),

  networkState: () =>
    request<{ status: string; network_state: NonNullable<AnalysisDoc["network_state"]> }>(
      "/api/network-state",
    ).then((r) => r.network_state),

  graph: () => request<{ status: string; graph?: PredictGraph }>("/api/graph").then((r) => r.graph),

  topology: () => request<TopologyData>("/api/topology"),

  entities: () =>
    request<{ status: string; entity_summary: { entity_count: number; entities: unknown[] } }>(
      "/api/entities",
    ).then((r) => r.entity_summary),

  entity: (id: string) =>
    request<{ status: string; entity: unknown }>(`/api/entities/${encodeURIComponent(id)}`).then(
      (r) => r.entity,
    ),

  edge: (src: string, dst: string) =>
    request<unknown>(`/api/edges/${encodeURIComponent(src)}/${encodeURIComponent(dst)}`),

  mitre: () =>
    request<{ status: string; trajectory?: MitreTrajectoryStep[] }>("/api/mitre").then((m) => ({
      status: "ok",
      trajectory: m.trajectory ?? [],
    })),

  counterfactual: () =>
    request<{ status: string; results?: Record<string, unknown>; recommendation?: unknown }>(
      "/api/counterfactual",
    ).then((r) => r),

  runCounterfactual: (action: string) =>
    request<{ status: string; results?: Record<string, unknown> }>(
      `/api/counterfactual/${action}`,
      { method: "POST" },
    ),

  // ── Live Monitoring (TShark) ─────────────────────────────

  liveHealth: () => request<LiveHealthInfo>("/api/live/health"),

  liveInterfaces: () =>
    request<{ interfaces: LiveInterface[] }>("/api/live/interfaces").then((r) => r.interfaces),

  liveStart: (cfg: { interface: string; window_size?: number; step_size?: number; forecast_horizon?: number }) =>
    request<LiveStartResponse>("/api/live/start", {
      method: "POST",
      body: JSON.stringify(cfg),
    }),

  liveStop: () =>
    request<{ status: string; analysis_id?: string; sensor_stats?: Record<string, unknown> }>(
      "/api/live/stop",
      { method: "POST" },
    ),

  liveStatus: () => request<LiveStatusResponse>("/api/live/status"),

  liveAnalysisDoc: (analysisId: string) =>
    request<LiveAnalysisDoc>(`/api/live/analysis/${encodeURIComponent(analysisId)}`),

  liveHistory: () =>
    request<{ sessions: LiveSessionHistory[] }>("/api/live/history").then((r) => r.sessions),

  liveEventsUrl: () => "/api/live/events",

  // ── URL Monitor (destination-observed live capture) ──────

  liveUrlStart: (cfg: UrlStartRequest) =>
    request<UrlStartResponse>("/api/live/url/start", {
      method: "POST",
      body: JSON.stringify(cfg),
    }),

  liveUrlStatus: (analysisId: string) =>
    request<UrlStatusResponse>(`/api/live/url/status/${encodeURIComponent(analysisId)}`),

  liveUrlStop: (analysisId?: string) =>
    request<{ status: string; analysis_id?: string; mode?: string; sensor_stats?: Record<string, unknown> }>(
      "/api/live/url/stop",
      { method: "POST", body: JSON.stringify({ analysis_id: analysisId }) },
    ),
};

export function favoriteFeaturePipeline(res: { status?: string }): boolean {
  return res.status === "ok";
}

export const downloadFile = async (url: string) => {
  const res = await fetch(url);
  const blob = await res.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = url.split("/").pop() ?? "report.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
};