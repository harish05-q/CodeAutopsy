"use client";

import { ArrowRight, Check, CircleDot, Clock3, Code2, GitFork, Play, Plus, Radar, ScanLine, Sparkles, X } from "lucide-react";
import { type ViewId } from "../mock-data";
import { type OverviewData } from "../api-client";

interface OverviewProps {
  onNavigate: (view: ViewId) => void;
  repoData: OverviewData;
  onNewCase: () => void;
}

export function Overview({ onNavigate, repoData, onNewCase }: OverviewProps) {
  // Use frameworks array
  const mainFramework = repoData.frameworks && repoData.frameworks.length > 0 
    ? repoData.frameworks[0] 
    : "Python Core";
    
  return (
    <>
      <section className="mb-8 flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span className="rounded-full bg-acid px-3 py-1 text-[10px] font-black uppercase tracking-[.14em]">Case File</span>
            <span className="text-xs font-medium text-ink/45">Analysis complete</span>
          </div>
          <h1 className="display max-w-3xl text-5xl font-semibold leading-[.94] sm:text-6xl xl:text-7xl">
            The codebase,<br /><span className="scribble italic">laid bare.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-sm leading-6 text-ink/55 sm:text-base">
            A living field report on {repoData.name}—its structure, pressure points, execution paths, and the shortest route to understanding it.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button 
            onClick={onNewCase} 
            className="group flex items-center gap-2 rounded-xl bg-ember px-5 py-3 text-sm font-bold text-white shadow-[4px_4px_0_#20241f] transition hover:-translate-y-0.5 hover:shadow-[6px_6px_0_#20241f] active:translate-y-0 active:shadow-[2px_2px_0_#20241f]"
          >
            <Plus size={17} />New examination
          </button>
          <button 
            onClick={() => onNavigate("onboarding")} 
            className="flex items-center gap-2 rounded-xl border border-ink/20 bg-white/55 px-5 py-3 text-sm font-bold transition hover:bg-white"
          >
            Open field guide <ArrowRight size={16} />
          </button>
        </div>
      </section>

      <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {repoData.stats.map((stat, index) => (
          <article key={stat.label} className="card group relative overflow-hidden p-4 sm:p-5">
            <span className={`absolute right-3 top-3 h-2.5 w-2.5 rounded-full ${index === 0 ? "bg-ember" : index === 1 ? "bg-mint" : index === 2 ? "bg-acid" : "bg-peach"}`} />
            <div className="display text-3xl font-bold sm:text-4xl">{stat.value}</div>
            <div className="mt-2 text-xs font-bold uppercase tracking-[.12em]">{stat.label}</div>
            <div className="mt-1 text-[11px] text-ink/40">{stat.note}</div>
            <div className="absolute inset-x-0 bottom-0 h-1 origin-left scale-x-0 bg-ink transition-transform duration-300 group-hover:scale-x-100" />
          </article>
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.3fr_.7fr]">
        <article className="card overflow-hidden">
          <div className="flex items-start justify-between border-b border-ink/10 p-5 sm:p-6">
            <div>
              <p className="eyebrow text-ember">Diagnosis</p>
              <h2 className="display mt-2 text-3xl font-bold">{repoData.architecture.pattern}</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-ink/50">{repoData.architecture.reasoning || "Automatic layout pattern deduced."}</p>
            </div>
            <div className="relative grid h-20 w-20 shrink-0 place-items-center rounded-full border-[7px] border-mint bg-paper text-center">
              <span className="text-xl font-black">{repoData.architecture.confidence}<span className="text-xs">%</span></span>
              <span className="absolute -bottom-6 whitespace-nowrap text-[9px] font-bold uppercase tracking-widest text-ink/40">Confidence</span>
            </div>
          </div>
          <div className="grid sm:grid-cols-3">
            {[
              ["Framework", mainFramework, Code2],
              ["Complexity Profile", `Avg: ${repoData.avg_complexity || 1.0}`, CircleDot],
              ["Primary flow", "Decoupled domain elements", GitFork]
            ].map(([label, value, Icon], index) => (
              <button 
                key={label as string} 
                onClick={() => onNavigate(index === 2 ? "dependencies" : "architecture")} 
                className="flex items-center gap-4 border-b border-ink/10 p-5 text-left transition hover:bg-acid/30 sm:border-b-0 sm:border-r last:border-0"
              >
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-paper"><Icon size={18} /></span>
                <span>
                  <span className="eyebrow block text-ink/35">{label as string}</span>
                  <span className="mt-1 block text-sm font-bold">{value as string}</span>
                </span>
              </button>
            ))}
          </div>
        </article>

        <article className="card bg-ink p-5 text-paper sm:p-6">
          <div className="flex items-center justify-between"><p className="eyebrow text-acid">Health reading</p><Radar className="text-acid" size={20} /></div>
          <div className="mt-7 flex items-end gap-3"><span className="display text-7xl font-bold">{repoData.maintainability_score}</span><span className="mb-2 text-sm text-paper/50">/ 100<br />maintainability</span></div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-paper/15"><div className="h-full rounded-full bg-gradient-to-r from-ember via-peach to-acid" style={{ width: `${repoData.maintainability_score}%` }} /></div>
          <div className="mt-5 flex justify-between text-xs"><span className="text-paper/45">Analysis Case File</span><button onClick={() => onNavigate("risks")} className="flex items-center gap-1 font-bold text-acid hover:underline">Inspect tissue <ArrowRight size={13} /></button></div>
        </article>
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-2">
        <article className="card p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="eyebrow text-ember">Recent activity</p>
              <h2 className="display mt-2 text-2xl font-bold">Execution log</h2>
            </div>
            <ScanLine size={22} className="text-ink/35" />
          </div>
          <div>
            {[
              ["Repository Cloned", "Shallow depth checkout completed", "0.0s"],
              ["AST Extraction", `${repoData.stats[1]?.value || 0} modules indexed`, "0.4s"],
              ["Relationship Graph", "Dependencies and approximate calls generated", "1.1s"],
              ["Static Quality", "Code metrics and hotspots isolated", "1.8s"],
              ["Semantic Embedding", "Syntax-aware chunks saved to FAISS", "2.5s"]
            ].map(([title, detail, time], index) => (
              <div key={title} className="relative flex gap-4 border-t border-ink/10 py-3.5 first:border-0">
                <div className={`mt-1 h-3 w-3 shrink-0 rounded-full border-2 border-paper ring-1 ring-ink/20 bg-mint`} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-bold">{title}</div>
                  <div className="truncate text-xs text-ink/45">{detail}</div>
                </div>
                <span className="font-mono text-[10px] text-ink/35">{time}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="eyebrow text-ember">Priority findings</p>
              <h2 className="display mt-2 text-2xl font-bold">Hot tissue</h2>
            </div>
            <button onClick={() => onNavigate("risks")} className="text-xs font-bold underline decoration-ember decoration-2 underline-offset-4">View all</button>
          </div>
          <div className="space-y-4">
            {repoData.hotspots && repoData.hotspots.length > 0 ? (
              repoData.hotspots.map((item) => (
                <button key={item.file} onClick={() => onNavigate("risks")} className="group block w-full text-left">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="truncate font-mono text-xs font-semibold">{item.file}</span>
                    <span className="rounded-full px-2 py-1 text-[9px] font-black uppercase tracking-wider" style={{ backgroundColor: `${item.color}25`, color: item.color }}>{item.risk}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-ink/8">
                    <div className="h-full rounded-full transition-all group-hover:brightness-90" style={{ width: `${item.score}%`, backgroundColor: item.color }} />
                  </div>
                </button>
              ))
            ) : (
              <div className="text-sm text-ink/40 font-medium py-8 text-center">No high-risk code hotspots found.</div>
            )}
          </div>
        </article>
      </section>
    </>
  );
}
