/**
 * API Client for CodeAutopsy Backend
 *
 * Type-safe HTTP client for all backend endpoints.
 * No wrapper magic — just fetch with types.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────

export interface RepoSubmitRequest {
  url: string;
}

export interface RepoSubmitResponse {
  analysis_id: number;
  repository_id: number;
  status: string;
  message: string;
}

export interface StageStatus {
  stage_name: string;
  status: string;
  duration_seconds: number | null;
  items_processed: number;
  summary: string | null;
  error_message: string | null;
}

export interface AnalysisStatus {
  analysis_id: number;
  repository_id: number;
  status: string;
  current_stage: string | null;
  progress_percent: number;
  started_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  stages: StageStatus[];
}

export interface RepositoryInfo {
  id: number;
  url: string;
  owner: string;
  name: string;
  total_files: number;
  total_lines: number;
  languages: string[];
  created_at: string;
}

export interface RiskFinding {
  category: string;
  severity: string;
  title: string;
  description: string;
  file_path: string;
  line_number: number | null;
  suggestion: string;
  evidence: Record<string, string | number>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  metadata: Record<string, string | number>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  weight: number;
}

export interface GraphData {
  graph_type: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: Record<string, string | number>;
}

// ── API Functions ─────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

/** Submit a repository for analysis */
export function submitRepo(url: string): Promise<RepoSubmitResponse> {
  return request<RepoSubmitResponse>("/api/repos", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

/** Get analysis status (poll this for progress) */
export function getAnalysisStatus(analysisId: number): Promise<AnalysisStatus> {
  return request<AnalysisStatus>(`/api/analysis/${analysisId}`);
}

/** List all repositories */
export function listRepos(): Promise<RepositoryInfo[]> {
  return request<RepositoryInfo[]>("/api/repos");
}

/** Get a single repository */
export function getRepo(repoId: number): Promise<RepositoryInfo> {
  return request<RepositoryInfo>(`/api/repos/${repoId}`);
}

/** Get dependency graph for a repo */
export function getDependencyGraph(repoId: number): Promise<GraphData> {
  return request<GraphData>(`/api/repos/${repoId}/graphs/dependency`);
}

/** Get call graph for a repo */
export function getCallGraph(repoId: number): Promise<GraphData> {
  return request<GraphData>(`/api/repos/${repoId}/graphs/call`);
}

/** Get graph analysis report */
export interface GraphAnalysisReport {
  dependency: GraphAnalysisSummary | null;
  call_graph: GraphAnalysisSummary | null;
}

export interface GraphAnalysisSummary {
  graph_type: string;
  summary: {
    total_nodes: number;
    total_edges: number;
    cycle_count: number;
    orphan_count: number;
    component_count: number;
    dead_code_candidates: number;
    coupled_pairs: number;
  };
  cycles: string[][];
  top_nodes_by_importance: { node: string; pagerank: number; in_degree: number; out_degree: number }[];
  highest_fan_out: { node: string; fan_in: number; fan_out: number }[];
  orphans: string[];
  tightly_coupled: { module_a: string; module_b: string }[];
  dead_code_candidates: string[];
}

export function getGraphAnalysis(repoId: number): Promise<GraphAnalysisReport> {
  return request<GraphAnalysisReport>(`/api/repos/${repoId}/graphs/analysis`);
}

/** Semantic Search */
export interface SearchResult {
  id: string;
  type: string;
  name: string;
  file_path: string;
  text_preview: string;
  score: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
}

export function searchCode(
  repoId: number,
  query: string,
  typeFilter?: string,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (typeFilter) {
    params.append("type", typeFilter);
  }
  return request<SearchResponse>(`/api/repos/${repoId}/search?${params.toString()}`);
}

/**
 * Fetch a specific JSON artifact from an analysis run.
 */
export function getArtifact<T = any>(analysisId: number, artifactName: string): Promise<T> {
  return request<T>(`/api/analysis/${analysisId}/artifacts/${artifactName}`);
}

/**
 * Download the generated PDF report programmatically.
 * Handles Blob conversion and prevents cross-origin routing issues.
 */
export async function downloadPdfReport(analysisId: number): Promise<void> {
  const url = `${API_BASE}/api/analysis/${analysisId}/report/download`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to download PDF: ${response.statusText}`);
  }

  // Create a Blob from the PDF stream
  const blob = await response.blob();
  
  // Extract filename from Content-Disposition header if available
  const disposition = response.headers.get("Content-Disposition");
  let filename = "autopsy_report.pdf";
  if (disposition && disposition.indexOf("filename=") !== -1) {
    const matches = /filename="([^"]+)"/.exec(disposition);
    if (matches && matches[1]) {
      filename = matches[1];
    }
  }

  // Create temporary link and trigger download
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = blobUrl;
  a.download = filename;
  
  document.body.appendChild(a);
  a.click();
  
  // Cleanup
  window.URL.revokeObjectURL(blobUrl);
  document.body.removeChild(a);
}
