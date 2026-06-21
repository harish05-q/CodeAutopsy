"use client";

import { useEffect, useState } from "react";
import { Clock3, Footprints } from "lucide-react";
import { fetchOnboarding } from "../api-client";
import { MarkdownRenderer } from "../markdown-renderer";

interface OnboardingProps {
  repoId: string;
}

export function Onboarding({ repoId }: OnboardingProps) {
  const [guide, setGuide] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [checklist, setChecklist] = useState<Array<{ text: string; done: boolean }>>([
    { text: "Orient the workspace & entrypoint", done: true },
    { text: "Trace request from endpoint to database", done: false },
    { text: "Inspect AST extraction logic", done: false },
    { text: "Verify test suite run results", done: false }
  ]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMsg("");

    async function loadOnboarding() {
      try {
        const data = await fetchOnboarding(repoId);
        if (active) {
          setGuide(data.content);
          setLoading(false);
        }
      } catch (err: any) {
        if (active) {
          setErrorMsg(err.message || "Failed to load onboarding field guide.");
          setLoading(false);
        }
      }
    }

    loadOnboarding();
    return () => { active = false; };
  }, [repoId]);

  const toggleCheck = (index: number) => {
    setChecklist(prev => prev.map((item, idx) => idx === index ? { ...item, done: !item.done } : item));
  };

  const progressPct = Math.round((checklist.filter(c => c.done).length / checklist.length) * 100);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <span className="h-8 w-8 animate-spin rounded-full border-4 border-ink/15 border-t-ember" />
        <span className="text-sm font-bold text-ink/50 uppercase tracking-widest">Authoring field guide...</span>
      </div>
    );
  }

  if (errorMsg || !guide) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center max-w-md mx-auto">
        <div className="text-ember font-bold mb-2">Error loading onboarding guide</div>
        <p className="text-xs text-ink/50 leading-5">{errorMsg || "No guide available."}</p>
      </div>
    );
  }

  return (
    <section>
      <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="eyebrow text-ember">Field onboarding</p>
          <h1 className="display mt-2 text-4xl font-bold sm:text-5xl">Your shortest path in.</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/50">
            A generated step-by-step reading guide to help you build working context in this repository under 60 minutes.
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-2xl border border-ink/15 bg-white/55 px-4 py-3 shrink-0">
          <Clock3 size={20} className="text-ember" />
          <div>
            <div className="text-sm font-black">~60 minutes</div>
            <div className="text-[10px] uppercase tracking-widest text-ink/40">to working context</div>
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[280px_1fr]">
        {/* Checklist Sidebar */}
        <article className="card overflow-hidden h-fit">
          <div className="border-b border-ink/10 bg-acid/55 p-5">
            <div className="flex items-center gap-2">
              <Footprints size={18} />
              <h2 className="display text-lg font-bold">Orientation Tasks</h2>
            </div>
            <p className="mt-1 text-[11px] text-ink/50">Check steps off as you orient yourself.</p>
          </div>
          <div className="p-3 space-y-1">
            {checklist.map((item, idx) => (
              <button 
                key={item.text} 
                onClick={() => toggleCheck(idx)}
                className="flex w-full items-start gap-2.5 rounded-xl p-2.5 text-left text-xs transition hover:bg-white/60"
              >
                <span className={`grid h-4 w-4 shrink-0 place-items-center rounded border text-[9px] font-bold ${item.done ? "border-ink bg-ink text-acid" : "border-ink/20 text-transparent"}`}>
                  ✓
                </span>
                <span className={`font-semibold ${item.done ? "line-through opacity-45" : "text-ink/85"}`}>
                  {item.text}
                </span>
              </button>
            ))}
          </div>
          <div className="mx-3 mb-3 p-3 rounded-xl bg-ink text-paper">
            <div className="mb-1 flex justify-between text-[9px] font-bold uppercase tracking-widest text-paper/70">
              <span>Task Progress</span>
              <span>{checklist.filter(c => c.done).length} / {checklist.length}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-paper/15">
              <div className="h-full bg-acid transition-all duration-300" style={{ width: `${progressPct}%` }} />
            </div>
          </div>
        </article>

        {/* Dynamic Markdown Guide content */}
        <article className="card p-6 sm:p-9 bg-white/55">
          <MarkdownRenderer content={guide} />
        </article>
      </div>
    </section>
  );
}
