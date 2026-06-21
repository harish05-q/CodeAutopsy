"use client";

import { useEffect, useState, useRef } from "react";
import { ArrowDown, CheckCircle2, Layers3, Lightbulb, Network, Quote, Server, ShieldCheck } from "lucide-react";
import { fetchArchitecture, type ArchitectureReport } from "../api-client";

interface ArchitectureProps {
  repoId: string;
}

const iconsMap: Record<string, any> = {
  "0": Server,
  "1": Network,
  "2": Layers3,
  "3": ShieldCheck,
};

export function Architecture({ repoId }: ArchitectureProps) {
  const [report, setReport] = useState<ArchitectureReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const mermaidRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMsg("");

    async function loadArchitecture() {
      try {
        const data = await fetchArchitecture(repoId);
        if (active) {
          setReport(data);
          setLoading(false);
        }
      } catch (err: any) {
        if (active) {
          setErrorMsg(err.message || "Failed to load architecture report.");
          setLoading(false);
        }
      }
    }

    loadArchitecture();
    return () => { active = false; };
  }, [repoId]);

  // Dynamically initialize and render Mermaid diagram
  useEffect(() => {
    if (!loading && report?.mermaid_diagram && mermaidRef.current) {
      // Clear previous content
      mermaidRef.current.innerHTML = `<div class="mermaid">${report.mermaid_diagram}</div>`;
      
      // Load and run mermaid compiler dynamically
      import("mermaid").then((m) => {
        m.default.initialize({ 
          startOnLoad: true,
          theme: "base",
          themeVariables: {
            background: "#faf8f1",
            primaryColor: "#d9ee68",
            primaryTextColor: "#20241f",
            lineColor: "#20241f",
            secondaryColor: "#f4b183",
            tertiaryColor: "#8bd3bd",
          }
        });
        m.default.contentLoaded();
      }).catch((e) => {
        console.error("Failed to load mermaid:", e);
      });
    }
  }, [loading, report]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <span className="h-8 w-8 animate-spin rounded-full border-4 border-ink/15 border-t-ember" />
        <span className="text-sm font-bold text-ink/50 uppercase tracking-widest">Inferring system patterns...</span>
      </div>
    );
  }

  if (errorMsg || !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center max-w-md mx-auto">
        <div className="text-ember font-bold mb-2">Error loading architecture report</div>
        <p className="text-xs text-ink/50 leading-5">{errorMsg || "No report available."}</p>
      </div>
    );
  }

  return (
    <section>
      <div className="mb-7">
        <p className="eyebrow text-ember">Pattern inference · {report.confidence}% confidence</p>
        <h1 className="display mt-2 text-4xl font-bold sm:text-5xl">Architecture report</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/50">{report.reasoning}</p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <article className="card p-5 sm:p-7">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="eyebrow text-ember">Structural section</p>
              <h2 className="display mt-2 text-3xl font-bold">{report.layers.length} discernible layers</h2>
            </div>
            <div className="hidden -rotate-2 rounded-xl border-2 border-ember px-3 py-2 text-[10px] font-black uppercase tracking-widest text-ember sm:block">Strong match</div>
          </div>
          <div className="space-y-2">
            {report.layers.map((layer, index) => {
              const Icon = iconsMap[String(index)] || Layers3;
              const colors = ["bg-peach", "bg-acid", "bg-mint", "bg-[#e3d3bc]"];
              const colorClass = colors[index % colors.length];
              
              return (
                <div key={layer.name}>
                  <div className={`${colorClass} group flex items-center gap-4 rounded-2xl border border-ink/15 p-4 transition hover:translate-x-1`}>
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-ink text-paper"><Icon size={19} /></span>
                    <div className="min-w-0 flex-1">
                      <div className="font-bold">{layer.name}</div>
                      <div className="truncate text-xs text-ink/50">{layer.detail}</div>
                    </div>
                    <span className="font-mono text-[10px] text-ink/35">0{index + 1}</span>
                  </div>
                  {index < report.layers.length - 1 && <ArrowDown size={16} className="mx-auto my-1 text-ink/30" />}
                </div>
              );
            })}
          </div>
        </article>

        <div className="space-y-5">
          <article className="card bg-ink p-6 text-paper">
            <Quote className="text-acid" size={26} />
            <p className="display mt-5 text-xl font-medium leading-snug">
              “{report.reasoning.split(".")[0]}. The architectural boundaries are mapped and structured.”
            </p>
            <div className="mt-6 flex items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-full bg-acid font-black text-ink">AI</span>
              <div>
                <div className="text-xs font-bold">Architecture Agent</div>
                <div className="text-[10px] text-paper/40">Inference pass complete</div>
              </div>
            </div>
          </article>

          <article className="card p-6">
            <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-mint"><Lightbulb size={18} /></span><div><p className="eyebrow text-ink/35">Key evidence</p><h3 className="font-bold">Why this diagnosis?</h3></div></div>
            <ul className="mt-5 space-y-3">
              {report.evidence.map((item) => (
                <li key={item} className="flex gap-3 text-sm leading-5 text-ink/60">
                  <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[#4f9d78]" />{item}
                </li>
              ))}
            </ul>
          </article>
        </div>
      </div>

      {/* Render Mermaid flow diagram */}
      <div className="card mt-5 p-6">
        <div className="mb-5">
          <p className="eyebrow text-ember">Visual diagram</p>
          <h2 className="display text-2xl font-bold">Structural boundaries</h2>
        </div>
        <div 
          ref={mermaidRef} 
          className="flex justify-center bg-[#faf8f1] border border-ink/10 rounded-2xl p-5 overflow-auto max-w-full"
        />
      </div>

      <article className="card mt-5 grid overflow-hidden md:grid-cols-3">
        <div className="bg-ember p-6 text-white">
          <p className="eyebrow text-white/60">Alternative pattern</p>
          <div className="display mt-3 text-3xl font-bold">{report.alternative_pattern}</div>
          <div className="mt-2 text-sm text-white/70">{report.alternative_confidence}% confidence</div>
        </div>
        <div className="p-6 md:col-span-2">
          <p className="text-sm leading-6 text-ink/60">{report.alternative_reasoning}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {[report.pattern, report.alternative_pattern, "Analyzed"].map((tag) => (
              <span key={tag} className="rounded-full border border-ink/15 bg-paper px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider">{tag}</span>
            ))}
          </div>
        </div>
      </article>
    </section>
  );
}
