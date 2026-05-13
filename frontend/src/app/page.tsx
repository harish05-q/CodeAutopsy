"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { submitRepo, listRepos, type RepositoryInfo } from "@/lib/api";
import { useEffect } from "react";

/**
 * Landing / Dashboard page.
 *
 * Two sections:
 * 1. Hero with repository URL submission form
 * 2. Previously analyzed repositories list
 */
export default function HomePage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [repos, setRepos] = useState<RepositoryInfo[]>([]);
  const router = useRouter();

  // Load previous analyses on mount
  useEffect(() => {
    listRepos()
      .then(setRepos)
      .catch(() => {}); // Silently fail if backend is down
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await submitRepo(url.trim());
      router.push(`/analysis/${result.analysis_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit repository");
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "60px 24px" }}>
      {/* Hero Section */}
      <div className="animate-fade-in" style={{ textAlign: "center", marginBottom: "56px" }}>
        <div
          style={{
            fontSize: "3.2rem",
            marginBottom: "12px",
          }}
        >
          🔬
        </div>
        <h1
          style={{
            fontSize: "2.8rem",
            fontWeight: 800,
            letterSpacing: "-0.03em",
            marginBottom: "16px",
            lineHeight: 1.1,
          }}
        >
          <span className="gradient-text">Code Autopsy</span>
        </h1>
        <p
          style={{
            color: "var(--text-secondary)",
            fontSize: "1.15rem",
            maxWidth: "600px",
            margin: "0 auto 40px",
            lineHeight: 1.6,
          }}
        >
          AI-powered architecture reverse-engineering. Analyze any GitHub repository for
          architecture patterns, dependency maps, risk analysis, and more.
        </p>

        {/* Submit Form */}
        <form
          onSubmit={handleSubmit}
          style={{
            display: "flex",
            gap: "12px",
            maxWidth: "640px",
            margin: "0 auto",
          }}
        >
          <input
            type="url"
            className="input-field"
            placeholder="https://github.com/owner/repository"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            style={{ flex: 1 }}
            id="repo-url-input"
          />
          <button
            type="submit"
            className="btn-primary"
            disabled={loading || !url.trim()}
            id="analyze-btn"
            style={{ whiteSpace: "nowrap" }}
          >
            {loading ? (
              <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    width: "16px",
                    height: "16px",
                    border: "2px solid rgba(255,255,255,0.3)",
                    borderTopColor: "white",
                    borderRadius: "50%",
                    animation: "spin-slow 0.8s linear infinite",
                    display: "inline-block",
                  }}
                />
                Analyzing...
              </span>
            ) : (
              "🔍 Analyze"
            )}
          </button>
        </form>

        {error && (
          <div
            style={{
              marginTop: "16px",
              padding: "12px 20px",
              background: "rgba(244, 63, 94, 0.1)",
              border: "1px solid rgba(244, 63, 94, 0.3)",
              borderRadius: "var(--radius-md)",
              color: "var(--accent-rose)",
              fontSize: "0.9rem",
            }}
          >
            {error}
          </div>
        )}
      </div>

      {/* Features Grid */}
      <div
        className="animate-slide-up"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "16px",
          marginBottom: "56px",
        }}
      >
        {[
          { icon: "🏗️", title: "Architecture", desc: "Infer patterns & module relationships" },
          { icon: "🕸️", title: "Dependency Maps", desc: "Visualize import & call graphs" },
          { icon: "⚠️", title: "Risk Analysis", desc: "Detect anti-patterns & code smells" },
          { icon: "🧠", title: "AI Insights", desc: "LLM-powered semantic summaries" },
          { icon: "🔍", title: "Semantic Search", desc: "Find related code by meaning" },
          { icon: "📄", title: "PDF Reports", desc: "Downloadable autopsy reports" },
        ].map((f) => (
          <div
            key={f.title}
            className="glass-card"
            style={{ padding: "24px", textAlign: "center" }}
          >
            <div style={{ fontSize: "1.8rem", marginBottom: "10px" }}>{f.icon}</div>
            <div style={{ fontWeight: 600, marginBottom: "6px", fontSize: "0.95rem" }}>
              {f.title}
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>
              {f.desc}
            </div>
          </div>
        ))}
      </div>

      {/* Previous Analyses */}
      {repos.length > 0 && (
        <div className="animate-slide-up">
          <h2
            style={{
              fontSize: "1.2rem",
              fontWeight: 600,
              marginBottom: "16px",
              color: "var(--text-secondary)",
            }}
          >
            Previous Analyses
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {repos.map((repo) => (
              <a
                key={repo.id}
                href={`/analysis/${repo.id}`}
                className="glass-card"
                style={{
                  padding: "16px 20px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  textDecoration: "none",
                  color: "inherit",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                    {repo.owner}/{repo.name || "analyzing..."}
                  </div>
                  <div
                    style={{
                      color: "var(--text-muted)",
                      fontSize: "0.82rem",
                      marginTop: "4px",
                    }}
                  >
                    {repo.total_files} files · {repo.total_lines.toLocaleString()} lines ·{" "}
                    {repo.languages.join(", ") || "scanning..."}
                  </div>
                </div>
                <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>→</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
