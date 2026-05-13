"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  getAnalysisStatus,
  getRepo,
  getGraphAnalysis,
  searchCode,
  getCallGraph,
  getDependencyGraph,
  downloadPdfReport,
  type AnalysisStatus,
  type RepositoryInfo,
  type GraphAnalysisReport,
  type SearchResult,
  type GraphData,
} from "@/lib/api";
import GraphViewer from "@/components/GraphViewer";
import RiskDashboard from "@/components/RiskDashboard";
import AutopsyReport from "@/components/AutopsyReport";

/**
 * Analysis dashboard page.
 *
 * Shows:
 * - Overall progress bar
 * - Pipeline stage timeline with status/timing
 * - Repository stats
 * - Error details if failed
 *
 * Polls the backend every 2 seconds while analysis is running.
 */
export default function AnalysisPage() {
  const params = useParams();
  const analysisId = Number(params.id);

  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [repo, setRepo] = useState<RepositoryInfo | null>(null);
  const [graphReport, setGraphReport] = useState<GraphAnalysisReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  // View State
  const [activeTab, setActiveTab] = useState<"overview" | "dependency" | "call" | "risks">("overview");
  const [depGraphData, setDepGraphData] = useState<GraphData | null>(null);
  const [callGraphData, setCallGraphData] = useState<GraphData | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getAnalysisStatus(analysisId);
      setStatus(data);
      // Fetch repo info once we have the repository_id
      if (data.repository_id && !repo) {
        const repoData = await getRepo(data.repository_id);
        setRepo(repoData);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch status");
    }
  }, [analysisId, repo]);

  // Poll while analysis is running
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(() => {
      if (status?.status === "completed" || status?.status === "failed") return;
      fetchStatus();
    }, 2000);
    return () => clearInterval(interval);
  }, [fetchStatus, status?.status]);

  // Fetch graph analysis once completed
  useEffect(() => {
    if (status?.status === "completed" && repo && !graphReport) {
      getGraphAnalysis(repo.id).then(setGraphReport).catch(() => {});
      getDependencyGraph(repo.id).then(setDepGraphData).catch(() => {});
      getCallGraph(repo.id).then(setCallGraphData).catch(() => {});
    }
  }, [status?.status, repo, graphReport]);

  const handleDownloadPdf = async (e: React.MouseEvent) => {
    e.preventDefault();
    try {
      await downloadPdfReport(analysisId);
    } catch (err) {
      console.error("Failed to download PDF", err);
      alert("Failed to download PDF report. It may still be generating.");
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim() || !repo) return;

    setIsSearching(true);
    setSearchError(null);

    try {
      const response = await searchCode(repo.id, searchQuery);
      setSearchResults(response.results);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Failed to search");
    } finally {
      setIsSearching(false);
    }
  };

  if (error) {
    return (
      <div style={{ maxWidth: "800px", margin: "60px auto", padding: "0 24px" }}>
        <div
          className="glass-card"
          style={{
            padding: "32px",
            textAlign: "center",
            borderColor: "rgba(244, 63, 94, 0.3)",
          }}
        >
          <div style={{ fontSize: "2rem", marginBottom: "12px" }}>❌</div>
          <h2 style={{ marginBottom: "8px" }}>Error Loading Analysis</h2>
          <p style={{ color: "var(--text-secondary)" }}>{error}</p>
          <a
            href="/"
            className="btn-primary"
            style={{ display: "inline-block", marginTop: "20px", textDecoration: "none" }}
          >
            ← Back to Dashboard
          </a>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div style={{ maxWidth: "800px", margin: "60px auto", padding: "0 24px", textAlign: "center" }}>
        <div
          style={{
            width: "40px",
            height: "40px",
            border: "3px solid var(--border-default)",
            borderTopColor: "var(--accent-primary)",
            borderRadius: "50%",
            animation: "spin-slow 0.8s linear infinite",
            margin: "0 auto 16px",
          }}
        />
        <p style={{ color: "var(--text-secondary)" }}>Loading analysis...</p>
      </div>
    );
  }

  const isRunning = !["completed", "failed"].includes(status.status);

  const statusBadgeClass =
    status.status === "completed"
      ? "badge-completed"
      : status.status === "failed"
        ? "badge-failed"
        : "badge-running";

  return (
    <div style={{ maxWidth: "800px", margin: "40px auto", padding: "0 24px" }}>
      {/* Header */}
      <div className="animate-fade-in" style={{ marginBottom: "32px" }}>
        <a
          href="/"
          style={{
            color: "var(--text-muted)",
            fontSize: "0.85rem",
            textDecoration: "none",
            marginBottom: "16px",
            display: "inline-block",
          }}
        >
          ← Back to Dashboard
        </a>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "8px",
          }}
        >
          <h1 style={{ fontSize: "1.6rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
            {repo ? `${repo.owner}/${repo.name}` : `Analysis #${analysisId}`}
          </h1>
          <div className="flex items-center gap-3">
            {status.status === "completed" && (
              <button
                onClick={handleDownloadPdf}
                className="btn-primary"
                style={{ display: "flex", alignItems: "center", gap: "6px", textDecoration: "none", cursor: "pointer" }}
              >
                <span>📄</span> Download PDF
              </button>
            )}
            <span className={`badge ${statusBadgeClass}`}>
              {isRunning && (
                <span
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: "currentColor",
                    animation: "pulse-glow 1.5s infinite",
                    display: "inline-block",
                  }}
                />
              )}
              {status.status}
            </span>
          </div>
        </div>

        {repo && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>{repo.url}</p>
        )}
      </div>

      {/* Progress Bar */}
      <div className="glass-card animate-fade-in" style={{ padding: "24px", marginBottom: "20px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: "10px",
            fontSize: "0.85rem",
          }}
        >
          <span style={{ color: "var(--text-secondary)" }}>
            {status.current_stage
              ? `Stage: ${status.current_stage.replace(/_/g, " ")}`
              : status.status === "completed"
                ? "All stages completed"
                : "Initializing..."}
          </span>
          <span style={{ color: "var(--accent-primary)", fontWeight: 600 }}>
            {Math.round(status.progress_percent)}%
          </span>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${status.progress_percent}%` }} />
        </div>
        {status.duration_seconds && (
          <div
            style={{
              marginTop: "8px",
              fontSize: "0.8rem",
              color: "var(--text-muted)",
              textAlign: "right",
            }}
          >
            Duration: {status.duration_seconds.toFixed(1)}s
          </div>
        )}
      </div>

      {/* Error Display */}
      {status.error_message && (
        <div
          className="glass-card animate-fade-in"
          style={{
            padding: "20px",
            marginBottom: "20px",
            borderColor: "rgba(244, 63, 94, 0.3)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
            <span style={{ fontSize: "1.2rem" }}>⚠️</span>
            <span style={{ fontWeight: 600, color: "var(--accent-rose)" }}>Error</span>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            {status.error_message}
          </p>
        </div>
      )}

      {/* Stats Grid */}
      {repo && (
        <div
          className="animate-slide-up"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "12px",
            marginBottom: "20px",
          }}
        >
          {[
            { label: "Files", value: repo.total_files, icon: "📁" },
            { label: "Lines", value: repo.total_lines.toLocaleString(), icon: "📝" },
            {
              label: "Languages",
              value: repo.languages.length || "—",
              icon: "🌐",
            },
            {
              label: "Risks",
              value: status.stages.find((s) => s.stage_name === "analyzing_ast")?.items_processed ?? "—",
              icon: "⚠️",
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="glass-card"
              style={{ padding: "16px", textAlign: "center" }}
            >
              <div style={{ fontSize: "1.3rem", marginBottom: "6px" }}>{stat.icon}</div>
              <div style={{ fontSize: "1.3rem", fontWeight: 700 }}>{stat.value}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      {status.status === "completed" && (
        <div className="flex gap-4 mb-6 mt-8 border-b border-gray-200">
          {[
            { id: "overview", label: "Overview" },
            { id: "dependency", label: "Dependency Graph" },
            { id: "call", label: "Call Graph" },
            { id: "risks", label: "Risk Assessment" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`pb-3 px-2 font-semibold text-sm transition-colors border-b-2 ${
                activeTab === tab.id
                  ? "border-rose-500 text-rose-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Tab Content */}
      {status.status === "completed" && activeTab === "overview" && (
        <div className="animate-fade-in">
          {/* Autopsy Report */}
          <AutopsyReport analysisId={analysisId} />

          {/* Graph Analysis Summary */}
          {graphReport && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                gap: "16px",
                marginBottom: "20px",
              }}
            >
              {/* Dependency Graph Card */}
              {graphReport.dependency && (
                <div className="glass-card" style={{ padding: "20px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
                    <span style={{ fontSize: "1.2rem" }}>🕸️</span>
                    <h3 style={{ fontSize: "0.95rem", fontWeight: 600 }}>Dependency Graph</h3>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                    {[
                      { label: "Modules", value: graphReport.dependency.summary.total_nodes },
                      { label: "Dependencies", value: graphReport.dependency.summary.total_edges },
                      { label: "Cycles", value: graphReport.dependency.summary.cycle_count, warn: graphReport.dependency.summary.cycle_count > 0 },
                      { label: "Dead Code", value: graphReport.dependency.summary.dead_code_candidates },
                    ].map((s) => (
                      <div key={s.label} style={{ padding: "8px", background: "var(--bg-secondary)", borderRadius: "var(--radius-sm)" }}>
                        <div style={{ fontSize: "1.1rem", fontWeight: 700, color: s.warn ? "var(--accent-rose)" : "var(--text-primary)" }}>{s.value}</div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Call Graph Card */}
              {graphReport.call_graph && (
                <div className="glass-card" style={{ padding: "20px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
                    <span style={{ fontSize: "1.2rem" }}>📞</span>
                    <h3 style={{ fontSize: "0.95rem", fontWeight: 600 }}>Call Graph</h3>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                    {[
                      { label: "Functions", value: graphReport.call_graph.summary.total_nodes },
                      { label: "Call Edges", value: graphReport.call_graph.summary.total_edges },
                      { label: "Cycles", value: graphReport.call_graph.summary.cycle_count, warn: graphReport.call_graph.summary.cycle_count > 0 },
                      { label: "Orphans", value: graphReport.call_graph.summary.orphan_count },
                    ].map((s) => (
                      <div key={s.label} style={{ padding: "8px", background: "var(--bg-secondary)", borderRadius: "var(--radius-sm)" }}>
                        <div style={{ fontSize: "1.1rem", fontWeight: 700, color: s.warn ? "var(--accent-rose)" : "var(--text-primary)" }}>{s.value}</div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Semantic Search Section */}
          {repo && (
            <div className="glass-card" style={{ padding: "24px", marginBottom: "20px" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px" }}>
                Semantic Search
              </h2>
              <form onSubmit={handleSearch} style={{ display: "flex", gap: "12px", marginBottom: "20px" }}>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g., 'how is authentication handled?' or 'database connection'"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ flex: 1 }}
                />
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={isSearching || !searchQuery.trim()}
                >
                  {isSearching ? "Searching..." : "Search"}
                </button>
              </form>

              {searchError && (
                <div style={{ color: "var(--accent-rose)", marginBottom: "16px", fontSize: "0.9rem" }}>
                  {searchError}
                </div>
              )}

              {searchResults && searchResults.length === 0 && (
                <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "20px 0" }}>
                  No semantic matches found.
                </div>
              )}

              {searchResults && searchResults.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {searchResults.map((res, i) => (
                    <div key={`${res.id}-${i}`} style={{ background: "var(--bg-secondary)", padding: "16px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-default)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                        <div style={{ fontWeight: 600, color: "var(--accent-primary)" }}>
                          {res.name} <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: "normal", marginLeft: "8px" }}>{res.type}</span>
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--accent-emerald)" }}>
                          {(res.score * 100).toFixed(1)}% match
                        </div>
                      </div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "8px", fontFamily: "monospace" }}>
                        {res.file_path}
                      </div>
                      <div style={{ fontSize: "0.9rem", color: "var(--text-primary)", whiteSpace: "pre-wrap", background: "var(--bg-primary)", padding: "12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-default)" }}>
                        {res.text_preview}...
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Pipeline Stages Timeline */}
          {status.stages.length > 0 && (
            <div className="glass-card" style={{ padding: "24px" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "20px" }}>
                Pipeline Stages
              </h2>
              <div className="stage-timeline">
                {status.stages.map((stage) => {
                  const dotClass =
                    stage.status === "completed"
                      ? "stage-dot-completed"
                      : stage.status === "failed"
                        ? "stage-dot-failed"
                        : "stage-dot-running";

                  return (
                    <div key={stage.stage_name} className="stage-item">
                      <div className={`stage-dot ${dotClass}`} />
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                            {stage.stage_name.replace(/_/g, " ")}
                          </div>
                          {stage.summary && (
                            <div
                              style={{
                                color: "var(--text-secondary)",
                                fontSize: "0.82rem",
                                marginTop: "4px",
                              }}
                            >
                              {stage.summary}
                            </div>
                          )}
                          {stage.error_message && (
                            <div
                              style={{
                                color: "var(--accent-rose)",
                                fontSize: "0.82rem",
                                marginTop: "4px",
                              }}
                            >
                              Error: {stage.error_message}
                            </div>
                          )}
                        </div>
                        <div style={{ textAlign: "right", flexShrink: 0, marginLeft: "16px" }}>
                          {stage.duration_seconds !== null && (
                            <div
                              style={{
                                color: "var(--text-muted)",
                                fontSize: "0.8rem",
                                fontFamily: "monospace",
                              }}
                            >
                              {stage.duration_seconds.toFixed(2)}s
                            </div>
                          )}
                          {stage.items_processed > 0 && (
                            <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                              {stage.items_processed} items
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {status.status === "completed" && activeTab === "dependency" && depGraphData && (
        <div className="animate-fade-in">
          <GraphViewer graphData={depGraphData} title="Dependency Graph" />
        </div>
      )}

      {status.status === "completed" && activeTab === "call" && callGraphData && (
        <div className="animate-fade-in">
          <GraphViewer graphData={callGraphData} title="Function Call Graph" />
        </div>
      )}

      {status.status === "completed" && activeTab === "risks" && (
        <div className="animate-fade-in">
          <RiskDashboard analysisId={analysisId} />
        </div>
      )}
    </div>
  );
}
