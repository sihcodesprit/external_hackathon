export type Severity = "LOW" | "GUARDED" | "ELEVATED" | "HIGH" | "CRITICAL";

export type ThreatLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "BENIGN";

export interface TrafficMember {
  name: string;
  size_bytes: number;
  kind: "pcap" | "pcapng" | "csv" | "jsonl";
}

export interface ZipInspect {
  filename: string;
  traffic_members: TrafficMember[];
  model_artifacts: string[];
  has_traffic: boolean;
  has_models: boolean;
  analysis?: string;
}

export interface ScenarioInfo {
  id: string;
  name: string;
  attack_types: string[];
  description: string;
}

export interface JobMeta {
  filename: string | null;
  member: string | null;
  source: string | null;
  occurrence: string | null;
  n_records: number | null;
  n_states: number | null;
  uploaded_at: string | null;
}

export interface JobPoll {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  stage: string;
  progress: number;
  message: string;
  error: string | null;
  result: AnalysisDoc | null;
  meta?: JobMeta;
}

export interface TrafficSummary {
  n_packets: number;
  n_bytes: number;
  n_flows: number;
  n_hosts: number;
  n_src_hosts: number;
  n_dst_hosts: number;
  n_unique_ports: number;
  duration_seconds: number;
  protocols: { protocol: string; count: number }[];
  attack_packets: number;
  benign_packets: number;
  attack_states: number;
  benign_states: number;
  stages_present: { stage: string; count: number }[];
  verdict?: { low: string; guarded: string; elevated: string; high: string; critical: string };
}

export interface NetworkStateRow {
  idx: number;
  timestamp: string;
  label: number;
  stage: string;
  traffic: Record<string, number>;
  tcp_handshake: Record<string, number>;
  entropy: Record<string, number>;
  temporal: Record<string, number>;
  graph: Record<string, number>;
  other: Record<string, number>;
}

export interface NetworkStateGroupDef {
  id: string;
  label: string;
  description: string | null;
}

export interface NetworkStatePayload {
  count: number;
  groups: NetworkStateGroupDef[];
  metric_labels: Record<string, string>;
  states: NetworkStateRow[];
}

export interface ForecastStep {
  step: number;
  stage: string;
  risk: number;
  key_risk_features?: string[];
}

export interface ForecastBlock {
  current: Record<string, number>;
  future: ForecastStep[];
  future_initial: Record<string, number>;
  final_prediction: string | null;
  description?: string;
}

export interface FeatureAttribution {
  feature: string;
  contribution: number;
  group?: string;
  description?: string;
}

export interface CounterfactualAction {
  action_id: string;
  label: string;
  description: string;
  final_risk: number;
  peak_risk: number;
  risk_trajectory: number[];
}

export interface CounterfactualResult {
  status: string;
  k: number;
  effect_window: number;
  baseline_current_risk: number;
  results: Record<string, CounterfactualAction>;
  recommendation: {
    status: string;
    recommended_action: string;
    recommended_label: string;
    baseline_risk: number;
    counterfactual_risk: number;
    risk_reduction: number;
    risk_reduction_pct_points: number;
    reason: string;
  };
}

export interface ForecastStep {
  step: number;
  stage: string;
  risk: number;
  confidence?: number;
  stage_probability?: number;
  features?: Record<string, number>;
}

export interface ForecastBlock {
  status: string;
  k: number;
  current: {
    risk: number;
    stage: string;
    confidence: number;
    features: Record<string, number>;
    state_vec?: number[];
    explanation?: {
      summary?: string;
      top_features?: Array<{ feature: string; contribution: number; description?: string }>;
    };
  };
  future: ForecastStep[];
  temporal_explanation?: unknown;
}

export interface PredictGraphNode {
  id: string;
  label: string;
  type: "current" | "predicted";
  severity: number;
  risk: number;
  probability: number;
  stage: string;
  step?: number;
  confidence?: number;
  evidence?: unknown[];
}

export interface PredictGraphEdge {
  id?: string;
  source: string;
  target: string;
  weight: number;
  label: string;
  transition?: boolean;
}

export interface GraphTimelineStep {
  step: number;
  stage: string;
  risk: number;
  confidence: number;
  probability: number;
}

export interface PredictGraph {
  nodes: PredictGraphNode[];
  edges: PredictGraphEdge[];
  counts: { nodes: number; edges: number; forecast_steps: number; stages: number; transitions: number };
  timeline?: GraphTimelineStep[];
  stages?: string[];
  stage_nodes?: PredictGraphNode[];
  stage_edges?: PredictGraphEdge[];
  benign_only?: boolean;
  unknown_stage?: boolean;
}

export interface EnsembleDetector {
  id: string;
  name: string;
  category: string;
  score: number;
  is_threat: boolean;
  verdict: string;
  badge: string;
  details: string;
  evidence?: string[];
  projected_stage?: string;
}

export interface EnsembleConsensus {
  score: number;
  score_raw: number;
  threat_level: ThreatLevel;
  threat_status: string;
  verdict_badge: string;
  agreement_count: number;
  total_detectors: number;
  agreement_pct: number;
  primary_stage: string;
  mitre: Record<string, unknown>;
  summary: string;
  recommendation: {
    recommended_action: string;
    action_label: string;
    reason: string;
    projected_risk_reduction_pct: number;
    simulated_future_risk: number;
  };
}

export interface RadarData {
  labels: string[];
  scores: number[];
}

export interface EnsembleResult {
  status: string;
  detectors: EnsembleDetector[];
  consensus: EnsembleConsensus;
  radar_data: RadarData;
}

export interface TopologyNode {
  entity_id: string;
  ip: string;
  hostname: string | null;
  entity_type: string;
  criticality: string;
  packet_count: number;
  byte_count: number;
  degree: number;
}

export interface TopologyEdge {
  src_id: string;
  dst_id: string;
  protocols: string[];
  ports: number[];
  packet_count: number;
  byte_count: number;
  first_seen: string | null;
  last_seen: string | null;
  duration: number;
  syn_count: number;
  syn_ack_count: number;
  ack_count: number;
  rst_count: number;
  fin_count: number;
  risk: number;
}

export interface TopologyData {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  counts: { nodes: number; edges: number };
}

export interface EntityData {
  entity_id: string;
  ip: string;
  hostname: string | null;
  entity_type: string;
  subnet: string | null;
  criticality: string;
  first_seen: string | null;
  last_seen: string | null;
  packet_count: number;
  byte_count: number;
  connections: number;
  unique_peers: number;
  unique_ports: number;
  syn_count: number;
  rst_count: number;
  fin_count: number;
}

export interface EntitySummary {
  entity_count: number;
  entities: EntityData[];
}

export interface MitreTrajectoryStep {
  stage: string;
  tactic: string;
  technique_id: string;
  technique_name: string;
  has_mitre: boolean;
}

export interface MitreIntegration {
  status?: string;
  trajectory: MitreTrajectoryStep[];
}

export interface ModelStatusEntry {
  name: string;
  display: string;
  status: string;
  type?: string;
  details?: string;
  seq?: number;
  metrics?: Record<string, number>;
}

export interface ModelStatus {
  registry_models: Record<string, unknown>[];
  artifacts: Array<{ name: string; size_kb: number; modified: string }>;
  active_traffic: {
    filename: string | null;
    member: string | null;
    source: string | null;
    occurrence: string | null;
    n_records: number;
    n_states: number;
    uploaded_at: string | null;
  };
}

export interface HistoryEntry {
  id: string;
  filename: string | null;
  member: string | null;
  source: string | null;
  occurrence: string | null;
  created_at: string;
  n_records: number;
  n_states: number;
  threat_level: ThreatLevel;
  threat_status: string;
  consensus_score: number;
  current_risk: number;
  forecast_risk: number;
  current_stage: string;
  predicted_stage: string;
}

export interface ModuleTestInfo {
  id: string;
  name: string;
  description: string;
  has_data: boolean;
}

export type ModuleTestResult = Record<string, unknown> & {
  status: string;
  module: string;
  message?: string;
  metrics?: Record<string, number>;
  steps?: Array<Record<string, unknown>>;
  trajectory?: MitreTrajectoryStep[];
  graph?: PredictGraph;
  counterfactual?: Record<string, unknown>;
  recommendation?: Record<string, unknown>;
  current?: unknown;
  temporal?: unknown;
};

export interface ModelTestModuleStatus {
  id: string;
  name: string;
  description: string;
  status: "queued" | "running" | "ok" | "failed" | "skipped";
  message?: string | null;
  metrics?: Record<string, number>;
  steps?: Array<Record<string, unknown>>;
  trajectory?: MitreTrajectoryStep[];
  graph?: PredictGraph;
  recommendation?: Record<string, unknown>;
  counterfactual?: Record<string, unknown>;
}

export interface ModelTestRunJob {
  job_id: string;
  status: string;
  progress: number;
  current_module: string | null;
  modules: ModelTestModuleStatus[];
  source: {
    filename?: string;
    member?: string | null;
    source?: string;
    n_records: number;
    n_states: number;
    n_flows: number;
  };
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at?: string;
  error?: string | null;
}

export interface ModelTestJobSummary {
  job_id: string;
  status: string;
  progress: number;
  current_module: string | null;
  created_at: string;
  finished_at: string | null;
  source: { filename?: string; member?: string | null; n_records: number; n_states: number; n_flows: number };
}

export interface ReportDocument {
  status: string;
  generated_at: string;
  source?: string | null;
  occurrence?: string | null;
  filename?: string | null;
  member?: string | null;
  file?: Record<string, unknown>;
  traffic_summary?: TrafficSummary;
  threat?: {
    threat_level: string;
    threat_status: string;
    consensus_score: number;
    agreement_pct: number;
    agreement_count: number;
    total_detectors: number;
    current_risk: number;
    forecast_risk: number;
    current_stage: string;
    predicted_stage: string;
    confidence: number;
    summary: string;
  };
  forecast?: {
    current: ForecastBlock["current"];
    future: ForecastStep[];
    steps: number;
  };
  mitre_trajectory?: MitreTrajectoryStep[];
  attack_graph?: PredictGraph;
  counterfactual?: CounterfactualResult;
  detectors?: EnsembleDetector[];
  recommendation?: {
    ensemble?: EnsembleConsensus["recommendation"];
    counterfactual?: CounterfactualResult["recommendation"];
  };
  evaluation?: unknown;
  models_status?: unknown[];
  explanation?: unknown;
  message?: string;
}

export interface AnalysisDoc {
  status: string;
  type: string;
  analysis_id?: string;
  filename: string | null;
  member: string | null;
  source: string | null;
  occurrence: string | null;
  n_records: number;
  n_states: number;
  error?: string;
  traffic_summary: TrafficSummary;
  network_state: NetworkStatePayload | null;
  forecast: ForecastBlock | null;
  graph: PredictGraph | null;
  counterfactual: CounterfactualResult | null;
  mitre_trajectory: MitreTrajectoryStep[] | null;
  ensemble: EnsembleResult | null;
  topology: TopologyData | null;
  entities: EntityData[] | null;
  state_groups: Record<string, string> | null;
  data_info: Record<string, unknown> | null;
  started_at?: string;
  finished_at?: string;
  elapsed_seconds?: number;
}

export interface ActiveAnalysisInfo {
  analysis_id: string | null;
  doc: AnalysisDoc | null;
}

export interface TestModuleInfo {
  module_id: string;
  name: string;
  description: string;
  severity: string;
  count: number;
  n_records: number;
  n_flows: number;
  n_states: number;
  n_hosts: number;
  detectors: string[];
  duration_minutes: number;
  file: string;
}

export interface TestModuleResult {
  status: string;
  module_id: string;
  name: string;
  n_states: number;
  n_records: number;
  forecast: ForecastBlock | null;
  ensemble: EnsembleResult | null;
  reception_matrix: Record<string, number> | null;
  confusion_matrix: Record<string, number> | null;
  per_stage_accuracy: Record<string, number> | null;
  overall_accuracy: number | null;
  report: {
    narrative: string | null;
    strengths: string[] | null;
    weaknesses: string[] | null;
  } | null;
  error?: string;
}

export interface ReportDocument {
  status: string;
  job_ids: number;
  n_records: number;
  n_states: number;
  threat_level: ThreatLevel;
  threat_score: number;
  ensemble_consensus: number | null;
  primary_stage: string | null;
  report: {
    title: string;
    subtitle: string;
    generated_at: string;
    executive_summary: string;
    data_overview: Record<string, unknown>;
    key_findings: string[];
    section: Array<{
      id: string;
      title: string;
      narrative: string;
      data?: Record<string, unknown>;
    }>;
    recommendations: string[];
    appendices: Array<{ id: string; title: string; narrative: string }>;
  } | null;
}

export interface SystemInfo {
  status: string;
  app: string;
  version: string;
  started_at: string;
  uptime_seconds: number;
  python: string;
  torch: string;
  numpy: string;
  world_model_type: string;
  features: string[];
}

export interface NetworkStateMetric {
  group: string;
  label: string;
  value: number;
  unit?: string;
}

// ── Live Monitoring (TShark) ───────────────────────────────

export type LiveStatus =
  | "stopped"
  | "starting"
  | "capturing"
  | "warming_up"
  | "analyzing"
  | "ready"
  | "stopping"
  | "error";

export interface LiveHealthInfo {
  available: boolean;
  path: string | null;
  version: string | null;
  error: string | null;
}

export interface LiveInterface {
  name: string;
  description: string;
  addresses: string[];
  is_up: boolean;
}

export interface LiveStartRequest {
  interface: string;
  window_size?: number;
  step_size?: number;
  forecast_horizon?: number;
}

export interface LiveStartResponse {
  analysis_id: string;
  status: string;
  mode?: string;
  interface?: string;
  sensor?: string;
  error?: string;
}

export interface LiveStatusResponse {
  active: boolean;
  status?: LiveStatus;
  analysis_id?: string;
  interface?: string;
  started_at?: string;
  uptime_seconds?: number;
  packets?: number;
  flows?: number;
  hosts?: number;
  states_count?: number;
  current_risk?: number;
  current_stage?: string;
  world_model_status?: string;
  last_error?: string;
  window_size?: number;
  step_size?: number;
  forecast_horizon?: number;
  tshark_stats?: Record<string, unknown>;
}

export interface LiveEvent {
  event_type: string;
  timestamp: string;
  [key: string]: unknown;
}

export interface LiveTelemetry {
  packets_per_second: number;
  bytes_per_second: number;
  events_per_second: number;
  window_count: number;
  current_window_events: number;
}

export interface LiveForecastPoint {
  step: number;
  risk: number;
  stage: string;
}

export interface LiveAnalysisDoc {
  analysis_id: string;
  source: string;
  interface: string;
  started_at: string;
  status: LiveStatus;
  uptime_seconds: number;
  telemetry: LiveTelemetry;
  current: {
    risk: number;
    stage: string;
    confidence: number;
    features: Record<string, number>;
  };
  forecast_steps: LiveForecastPoint[];
  risk_history: Array<{ timestamp: string; risk: number }>;
  ensemble?: EnsembleResult;
  counterfactual?: CounterfactualResult;
  mitre_trajectory?: MitreTrajectoryStep[];
  graph?: PredictGraph;
  event_log: LiveEvent[];
  states_count: number;
  packets: number;
  flows: number;
  hosts: number;
}

export interface LiveSessionHistory {
  analysis_id: string;
  interface: string;
  started_at: string;
  stopped_at: string | null;
  packets: number;
  flows: number;
  hosts: number;
  states: number;
  world_model_status: string;
}

// ── URL Monitor (destination-observed live capture) ────────

export interface UrlTargetInfo {
  url: string;
  hostname: string;
  scheme: string;
  port: number;
  path: string;
  protocol: string;
  resolved_ips: string[];
  previous_ips: string[];
  ip_history: Array<{ resolved_at: number | null; ips: string[] }>;
  resolution_count: number;
}

export interface UrlTraffic {
  packets: number;
  bytes: number;
  flows: number;
  packets_per_second: number;
  bytes_per_second: number;
  upload_rate: number;
  download_rate: number;
  outbound_packets: number;
  outbound_bytes: number;
  inbound_packets: number;
  inbound_bytes: number;
  syn_count: number;
  rst_count: number;
  fin_count: number;
  retransmissions: number;
  tls_connections: number;
  resolutions: number;
  target_ip_changes: number;
  active_connections: number;
}

export interface UrlTimelineEvent {
  timestamp: string;
  type: string;
  message: string;
  data?: Record<string, unknown>;
}

export interface UrlRiskBlock {
  current_risk?: number;
  future_max_risk?: number;
  risk_trend?: string;
  confidence?: number;
  forecast_horizon?: number;
}

export interface UrlForecastPoint {
  step?: number;
  risk?: number;
  stage?: string;
  confidence?: number;
  stage_probability?: number;
}

export interface UrlStartRequest {
  url: string;
  interface: string;
  window_size?: number;
  step_size?: number;
  forecast_horizon?: number;
}

export interface UrlStartResponse {
  analysis_id: string;
  mode: string;
  status: string;
  url?: string;
  hostname?: string;
  interface?: string;
  sensor?: string;
  target?: UrlTargetInfo;
  error?: string;
}

export interface UrlStatusResponse {
  analysis_id: string;
  mode: string;
  status: LiveStatus;
  interface: string;
  sensor?: string;
  started_at?: string;
  source?: { type: string; url: string; interface: string } | null;
  target: UrlTargetInfo | null;
  traffic: UrlTraffic;
  url_metrics?: Record<string, unknown>;
  timeline: UrlTimelineEvent[];
  network_state?: { features?: Record<string, number>; timestamp?: string } | null;
  risk: UrlRiskBlock;
  forecast: { current?: Record<string, unknown>; future?: UrlForecastPoint[] } | null;
  stage: Record<string, unknown>;
  graph: PredictGraph | null;
  mitre: MitreTrajectoryStep[] | null;
  explainability: Record<string, unknown>;
  counterfactual: Record<string, unknown>;
  ensemble?: EnsembleResult | null;
  world_model_status?: string;
}