export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export interface AnalyzeResponse {
  repository_id: string;
  run_id: string;
  status: string;
}

export interface OverviewStats {
  value: string;
  label: string;
  note: string;
}

export interface OverviewData {
  repository_id: string;
  name: string;
  owner: string;
  url: string;
  stats: OverviewStats[];
  frameworks: string[];
  architecture: {
    pattern: string;
    confidence: number;
    reasoning: string;
  };
  maintainability_score: number;
  avg_complexity: number;
  hotspots: Array<{ file: string; risk: string; score: number; color: string }>;
  status: string;
  stage: string;
  progress: number;
}

export interface GraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    kind: string;
    files: number;
    tone: string;
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  animated: boolean;
  style: { stroke: string; strokeWidth: number };
  markerEnd: { type: string; color: string };
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ArchitectureReport {
  pattern: string;
  confidence: number;
  reasoning: string;
  layers: Array<{ name: string; detail: string }>;
  evidence: string[];
  alternative_pattern: string;
  alternative_confidence: number;
  alternative_reasoning: string;
  mermaid_diagram: string;
}

export interface OnboardingResponse {
  content: string;
}

export interface Finding {
  type: string;
  location: string;
  advice: string;
  risk: string;
  file_path: string;
  line: number | null;
}

export interface RisksResponse {
  maintainability_score: number;
  avg_complexity: number;
  findings: Finding[];
  hotspots: Array<{ file: string; risk: string; score: number; color: string }>;
}

export interface ChatSource {
  file_path: string;
  line_interval: [number, number];
  symbol: string;
  relevance_score: number;
}

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  confidence: string;
  sources: ChatSource[];
}

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const key = localStorage.getItem("groq_api_key");
    if (key) {
      headers["X-Groq-API-Key"] = key;
    }
  }
  return headers;
}

/**
 * Initiates an analysis run for a given repository.
 */
export async function analyzeRepository(url: string, ref: string = "main"): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/repositories/analyze`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ url, ref })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to trigger repository analysis");
  }
  return res.json();
}

/**
 * Fetches the overview details for a repository.
 */
export async function fetchOverview(repoId: string): Promise<OverviewData> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/overview`);
  if (!res.ok) throw new Error("Failed to fetch repository overview");
  return res.json();
}

/**
 * Fetches the dependency graph.
 */
export async function fetchDependencyGraph(repoId: string): Promise<GraphResponse> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/graphs/dependencies`);
  if (!res.ok) throw new Error("Failed to fetch dependency graph");
  return res.json();
}

/**
 * Fetches the call graph.
 */
export async function fetchCallGraph(repoId: string): Promise<GraphResponse> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/graphs/calls`);
  if (!res.ok) throw new Error("Failed to fetch call graph");
  return res.json();
}

/**
 * Fetches the architecture report.
 */
export async function fetchArchitecture(repoId: string): Promise<ArchitectureReport> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/architecture`);
  if (!res.ok) throw new Error("Failed to fetch architecture report");
  return res.json();
}

/**
 * Fetches the onboarding guide.
 */
export async function fetchOnboarding(repoId: string): Promise<OnboardingResponse> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/onboarding`);
  if (!res.ok) throw new Error("Failed to fetch onboarding guide");
  return res.json();
}

/**
 * Fetches risks and hotspots.
 */
export async function fetchRisks(repoId: string): Promise<RisksResponse> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/risks`);
  if (!res.ok) throw new Error("Failed to fetch risks analysis");
  return res.json();
}

/**
 * Sends a QA chatbot query.
 */
export async function sendChatMessage(
  repoId: string,
  question: string,
  conversationId: string | null = null
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/chat`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ question, conversation_id: conversationId })
  });
  if (!res.ok) throw new Error("Failed to send message to code assistant");
  return res.json();
}
