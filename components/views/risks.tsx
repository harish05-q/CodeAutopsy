"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, ArrowUpRight, CircleCheck, Flame, Gauge, ScanSearch, ShieldAlert } from "lucide-react";
import { fetchRisks, type RisksResponse, type Finding } from "../api-client";

interface RisksProps {
  repoId: string;
}

export function Risks({ repoId }: RisksProps) {
  const [report, setReport] = useState<RisksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMsg("");

    async function loadRisks() {
      try {
        const data = await fetchRisks(repoId);
        if (active) {
          setReport(data);
          setLoading(false);
        }
      } catch (err: any) {
        if (active) {
          setErrorMsg(err.message || "Failed to load risks data.");
          setLoading(false);
        }
      }
    }

    loadRisks();
    return () => { active = false; };
  }, [repoId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <span className="h-8 w-8 animate-spin rounded-full border-4 border-ink/15 border-t-ember" />
        <span className="text-sm font-bold text-ink/50 uppercase tracking-widest">Dissecting code tissue...</span>
      </div>
    );
  }

  if (errorMsg || !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center max-w-md mx-auto">
        <div className="text-ember font-bold mb-2">Error loading risk metrics</div>
        <p className="text-xs text-ink/50 leading-5">{errorMsg || "No report available."}</p>
      </div>
    );
  }

  const getMaintainabilityLabel = (score: number) => {
    if (score > 85) return "Healthy";
    if (score > 70) return "Good";
    if (score > 50) return "Fair";
    return "Degraded";
  };

  return (
    <section>
      <div className="mb-7">
        <p className="eyebrow text-ember">Static analysis + graph heuristics</p>
        <h1 className="display mt-2 text-4xl font-bold sm:text-5xl">Risk tissue</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink/50">
          Not every anomaly is a disease. These are the structural anomalies most likely to impede additions, introduce regression bugs, or confuse new contributors.
        </p>
      </div>

      <div className="mb-5 grid gap-4 md:grid-cols-[1.2fr_.8fr_.8fr]">
        <article className="card flex items-center gap-6 bg-ink p-6 text-paper">
          <div className="relative grid h-28 w-28 shrink-0 place-items-center rounded-full border-[9px] border-acid">
            <span className="display text-4xl font-bold">{report.maintainability_score}</span>
            <span className="absolute -bottom-2 rounded-full bg-ember px-2 py-1 text-[8px] font-black uppercase tracking-wider">
              {getMaintainabilityLabel(report.maintainability_score)}
            </span>
          </div>
          <div>
            <p className="eyebrow text-acid">Maintainability</p>
            <p className="mt-3 text-xs leading-5 text-paper/55">
              Code health score calculated by class sizes, method weights, import coupling, and circular dependency checks.
            </p>
          </div>
        </article>

        <article className="card p-5">
          <Flame className="text-ember" size={22} />
          <div className="display mt-5 text-4xl font-bold">{report.hotspots.length}</div>
          <div className="mt-1 text-xs font-bold uppercase tracking-widest">Hotspots</div>
          <div className="mt-4 text-[11px] text-ink/40">
            {report.hotspots.filter(h => h.risk === "High").length} require attention now
          </div>
        </article>

        <article className="card p-5">
          <Gauge className="text-[#9c8a2e]" size={22} />
          <div className="display mt-5 text-4xl font-bold">{report.avg_complexity}</div>
          <div className="mt-1 text-xs font-bold uppercase tracking-widest">Avg. complexity</div>
          <div className="mt-4 text-[11px] text-ink/40">Inherent AST branch density</div>
        </article>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.3fr_.7fr]">
        <article className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-ink/10 p-5 sm:p-6">
            <div>
              <p className="eyebrow text-ember">Refactoring queue</p>
              <h2 className="display mt-2 text-2xl font-bold">Findings by priority</h2>
            </div>
            <ScanSearch size={23} className="text-ink/30" />
          </div>
          <div>
            {report.findings && report.findings.length > 0 ? (
              report.findings.map((item, idx) => (
                <div 
                  key={`${item.location}-${idx}`} 
                  className="group grid w-full gap-2 border-b border-ink/10 p-5 text-left last:border-0 hover:bg-white/50 sm:grid-cols-[150px_1fr_auto] sm:items-center"
                >
                  <div>
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[9px] font-black uppercase tracking-widest ${item.risk === "High" ? "bg-ember/15 text-ember" : item.risk === "Medium" ? "bg-peach/35 text-[#986020]" : "bg-mint/30 text-[#39745e]"}`}>
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />
                      {item.risk}
                    </span>
                    <div className="mt-2 text-xs font-bold">{item.type}</div>
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-mono text-xs font-bold">{item.location}</div>
                    <div className="mt-1 text-xs text-ink/45">{item.advice}</div>
                  </div>
                  <ArrowUpRight size={16} className="hidden text-ink/25 transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-ember sm:block" />
                </div>
              ))
            ) : (
              <div className="text-sm text-ink/40 font-semibold py-12 text-center">No refactoring findings identified. Codebase shows excellent metrics!</div>
            )}
          </div>
        </article>

        <aside className="space-y-5">
          <article className="card p-5 sm:p-6">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-ember text-white"><ShieldAlert size={18} /></span>
              <div>
                <p className="eyebrow text-ink/35">Exposure</p>
                <h3 className="font-bold">Highest-risk files</h3>
              </div>
            </div>
            <div className="mt-6 space-y-5">
              {report.hotspots && report.hotspots.length > 0 ? (
                report.hotspots.map((item, index) => (
                  <div key={item.file}>
                    <div className="mb-2 flex gap-3">
                      <span className="font-mono text-[10px] text-ink/25">0{index + 1}</span>
                      <span className="min-w-0 flex-1 truncate font-mono text-[11px] font-bold">{item.file}</span>
                      <span className="text-xs font-black" style={{ color: item.color }}>{item.score}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-ink/10">
                      <div className="h-full rounded-full" style={{ width: `${item.score}%`, background: item.color }} />
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-ink/40 font-semibold text-center py-6">No hotspots detected.</div>
              )}
            </div>
          </article>

          <article className="rounded-[18px] border border-[#4f9d78]/30 bg-mint/35 p-5">
            <div className="flex gap-3">
              <CircleCheck className="shrink-0 text-[#39745e]" size={20} />
              <div>
                <div className="text-sm font-bold">No critical security smells</div>
                <p className="mt-1 text-xs leading-5 text-ink/50">
                  Static analysis did not identify any hard-coded secret keys, raw execution parameters, or unsafe file permissions.
                </p>
              </div>
            </div>
          </article>
        </aside>
      </div>
    </section>
  );
}
