"use client";

import { useState, useEffect } from "react";
import { 
  ArrowUpRight, BookOpen, Boxes, Braces, CircleHelp, Command, 
  FileCode2, GitBranch, HeartPulse, Menu, MessageCircle, 
  PanelLeftClose, Search, Settings2, ShieldAlert, Sparkles, X, Play, Check, Clock3
} from "lucide-react";
import { navItems, type ViewId } from "./mock-data";
import { Overview } from "./views/overview";
import { GraphView } from "./views/graph-view";
import { Architecture } from "./views/architecture";
import { Onboarding } from "./views/onboarding";
import { Risks } from "./views/risks";
import { Chat } from "./views/chat";
import { fetchOverview, analyzeRepository, API_BASE, type OverviewData } from "./api-client";

const icons = { 
  overview: BookOpen, 
  dependencies: Boxes, 
  calls: GitBranch, 
  architecture: Braces, 
  onboarding: FileCode2, 
  risks: ShieldAlert, 
  chat: MessageCircle 
};

export function Dashboard() {
  const [view, setView] = useState<ViewId>("overview");
  const [sidebar, setSidebar] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  
  // Dynamic case state
  const [repoId, setRepoId] = useState<string | null>(null);
  const [repoData, setRepoData] = useState<OverviewData | null>(null);
  
  // Analysis running states
  const [newCase, setNewCase] = useState(false);
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("main");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("idle");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  
  // Custom API configurations
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");

  // Load API Key on client-side mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      setApiKeyInput(localStorage.getItem("groq_api_key") || "");
    }
  }, []);

  const saveSettings = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem("groq_api_key", apiKeyInput);
      setSettingsOpen(false);
      alert("System configuration updated successfully!");
    }
  };

  const selectView = (id: ViewId) => { 
    setView(id); 
    setSidebar(false); 
    setCommandOpen(false); 
  };

  // Helper to load repository overview
  const loadRepository = async (id: string) => {
    try {
      const data = await fetchOverview(id);
      setRepoData(data);
      setRepoId(id);
    } catch (err) {
      console.error("Error fetching overview data:", err);
    }
  };

  // Submits repository analysis and listens to SSE stream
  const triggerAnalysis = async () => {
    if (!url.trim()) return;
    setIsAnalyzing(true);
    setProgress(0);
    setStage("submitting");
    setErrorMsg("");
    
    try {
      const response = await analyzeRepository(url, ref);
      const runId = response.run_id;
      const repositoryId = response.repository_id;

      // Subscribe to Server Sent Events
      const eventSource = new EventSource(`${API_BASE}/analysis/${runId}/events`);
      
      eventSource.addEventListener("stage.progress", (event: any) => {
        try {
          const payload = JSON.parse(event.data);
          setProgress(payload.progress);
          setStage(payload.stage);
          
          if (payload.status === "completed") {
            eventSource.close();
            setIsAnalyzing(false);
            setNewCase(false);
            loadRepository(repositoryId);
          } else if (payload.status === "failed") {
            eventSource.close();
            setIsAnalyzing(false);
            setErrorMsg(payload.error_code || "Analysis failed.");
          }
        } catch (e) {
          console.error("Error parsing progress event:", e);
        }
      });

      eventSource.onerror = (err) => {
        console.error("SSE Connection error:", err);
        eventSource.close();
        setIsAnalyzing(false);
        setErrorMsg("Lost connection to analysis server.");
      };

    } catch (err: any) {
      setIsAnalyzing(false);
      setErrorMsg(err.message || "Failed to start analysis.");
    }
  };

  const getStageLabel = (currentStage: string) => {
    switch (currentStage) {
      case "clone": return "Cloning repository";
      case "ast": return "Extracting AST symbols";
      case "graph": return "Constructing relationship graphs";
      case "embed": return "Creating semantic embeddings & FAISS index";
      case "report": return "Authoring architecture & onboarding documentation";
      case "complete": return "Analysis complete";
      case "submitting": return "Enqueuing case file";
      default: return "Processing codebase";
    }
  };

  return (
    <div className="grain min-h-screen bg-paper text-ink">
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-[278px] flex-col border-r border-ink/15 bg-[#ebe6d8] p-4 transition-transform duration-300 lg:translate-x-0 ${sidebar ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-16 items-center justify-between px-2">
          <button onClick={() => selectView("overview")} className="flex items-center gap-3 text-left">
            <span className="grid h-10 w-10 rotate-3 place-items-center rounded-xl bg-ember text-paper shadow-[3px_3px_0_#20241f]">
              <HeartPulse size={21} strokeWidth={2.4} />
            </span>
            <span>
              <span className="display block text-xl font-bold leading-none">CodeAutopsy</span>
              <span className="mt-1 block text-[9px] font-bold uppercase tracking-[.2em] text-ink/50">Repository intelligence</span>
            </span>
          </button>
          <button className="p-2 lg:hidden" onClick={() => setSidebar(false)} aria-label="Close menu"><X size={20} /></button>
        </div>

        <div className="mt-5 rounded-2xl border border-ink/15 bg-paper/70 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="eyebrow text-ink/45">Case file</span>
            <span className={`relative h-2 w-2 rounded-full pulse-dot ${repoId ? "bg-[#4f9d78] text-[#4f9d78]" : "bg-ink/20 text-ink/20"}`} />
          </div>
          {repoData ? (
            <button onClick={() => setNewCase(true)} className="flex w-full items-center gap-3 rounded-xl bg-white/60 px-3 py-3 text-left transition hover:bg-white">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink text-acid"><Command size={15} /></span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-bold">{repoData.owner} / {repoData.name}</span>
                <span className="text-[11px] text-ink/50">branch · analyzed recently</span>
              </span>
              <ArrowUpRight size={14} className="text-ink/40" />
            </button>
          ) : (
            <button onClick={() => setNewCase(true)} className="flex w-full items-center gap-3 rounded-xl bg-white/30 px-3 py-3 text-left transition hover:bg-white border-2 border-dashed border-ink/15">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink/10 text-ink/40"><Command size={15} /></span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-bold text-ink/65">No case loaded</span>
                <span className="text-[11px] text-ink/40">Dissect a repo now</span>
              </span>
              <PlusIcon size={14} className="text-ink/30" />
            </button>
          )}
        </div>

        <nav className="mt-6 flex-1 space-y-1 overflow-auto no-scrollbar">
          <p className="eyebrow mb-3 px-3 text-ink/35">Examination</p>
          {navItems.map((item) => {
            const Icon = icons[item.id];
            const active = view === item.id;
            return (
              <button 
                key={item.id} 
                onClick={() => repoId ? selectView(item.id) : setNewCase(true)} 
                disabled={!repoId && item.id !== "overview"}
                className={`group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${active ? "bg-ink text-paper" : "text-ink/65 hover:bg-white/60 hover:text-ink"} disabled:opacity-40`}
              >
                <Icon size={17} strokeWidth={active ? 2.4 : 1.8} />
                <span className="flex-1 font-semibold">{item.label}</span>
                <span className={`font-mono text-[9px] ${active ? "text-acid" : "text-ink/30 group-hover:text-ink/50"}`}>{item.index}</span>
              </button>
            );
          })}
        </nav>

        <div className="space-y-1 border-t border-ink/10 pt-3">
          <button onClick={() => setSettingsOpen(true)} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-ink/55 hover:bg-white/60 hover:text-ink"><Settings2 size={17} />Settings</button>
          <button onClick={() => setInfoOpen(true)} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-ink/55 hover:bg-white/60 hover:text-ink"><CircleHelp size={17} />How it works</button>
        </div>
      </aside>

      {sidebar && <button onClick={() => setSidebar(false)} className="fixed inset-0 z-40 bg-ink/30 backdrop-blur-sm lg:hidden" aria-label="Close navigation" />}

      <main className="min-h-screen lg:pl-[278px]">
        <header className="sticky top-0 z-30 flex h-[76px] items-center gap-3 border-b border-ink/10 bg-paper/85 px-4 backdrop-blur-xl sm:px-7 lg:px-10">
          <button onClick={() => setSidebar(true)} className="rounded-lg p-2 hover:bg-ink/5 lg:hidden" aria-label="Open menu"><Menu size={21} /></button>
          <div className="min-w-0 flex-1">
            <div className="eyebrow mb-1 text-ember">Live examination</div>
            {repoData ? (
              <div className="truncate text-sm font-semibold text-ink/65">
                github.com/{repoData.owner}/{repoData.name} <span className="text-ink/30">/</span> <span className="text-ink">{navItems.find((item) => item.id === view)?.label}</span>
              </div>
            ) : (
              <div className="truncate text-sm font-semibold text-ink/40">Select or upload a repository to inspect</div>
            )}
          </div>
          <button onClick={() => setCommandOpen(true)} className="hidden min-w-[230px] items-center gap-2 rounded-xl border border-ink/15 bg-white/50 px-3 py-2.5 text-left text-xs text-ink/45 transition hover:border-ink/30 hover:bg-white sm:flex">
            <Search size={15} /><span className="flex-1">Jump to anything</span><kbd className="rounded border border-ink/15 bg-paper px-1.5 py-0.5 font-mono text-[9px]">⌘ K</kbd>
          </button>
          <button className="relative grid h-10 w-10 place-items-center rounded-full border border-ink/15 bg-mint text-sm font-black transition hover:-rotate-3">HA<span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-paper bg-ember" /></button>
        </header>

        <div className="paper-grid min-h-[calc(100vh-76px)] p-4 sm:p-7 lg:p-10">
          <div key={view} className="mx-auto max-w-[1440px] reveal">
            {repoId && repoData ? (
              <>
                {view === "overview" && <Overview onNavigate={selectView} repoData={repoData} onNewCase={() => setNewCase(true)} />}
                {view === "dependencies" && <GraphView kind="dependencies" repoId={repoId} />}
                {view === "calls" && <GraphView kind="calls" repoId={repoId} />}
                {view === "architecture" && <Architecture repoId={repoId} />}
                {view === "onboarding" && <Onboarding repoId={repoId} />}
                {view === "risks" && <Risks repoId={repoId} />}
                {view === "chat" && <Chat repoId={repoId} />}
              </>
            ) : (
              // Welcome / Landing Empty State
              <div className="flex flex-col items-center justify-center min-h-[50vh] text-center max-w-xl mx-auto py-12">
                <span className="grid h-16 w-16 rotate-6 place-items-center rounded-2xl bg-acid text-ink shadow-[4px_4px_0_#20241f] mb-8">
                  <Sparkles size={28} />
                </span>
                <h1 className="display text-4xl font-semibold leading-[.96] mb-4">No repository dissected yet.</h1>
                <p className="text-sm leading-6 text-ink/55 mb-8">Paste a public GitHub repository link below to clone, index, and analyze it with static analysis graphs and Groq LLM intelligence.</p>
                <button 
                  onClick={() => setNewCase(true)} 
                  className="px-6 py-3.5 bg-ember font-bold text-white rounded-xl shadow-[4px_4px_0_#20241f] transition hover:-translate-y-0.5 hover:shadow-[6px_6px_0_#20241f] active:translate-y-0 active:shadow-[2px_2px_0_#20241f] flex items-center gap-2"
                >
                  Start new examination
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      {commandOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-start bg-ink/35 px-4 pt-[12vh] backdrop-blur-sm" onMouseDown={() => setCommandOpen(false)}>
          <div onMouseDown={(event) => event.stopPropagation()} className="w-full max-w-xl overflow-hidden rounded-2xl border border-ink/20 bg-[#faf8f1] shadow-2xl">
            <div className="flex items-center gap-3 border-b border-ink/10 px-5 py-4"><Search size={18} /><input autoFocus className="w-full bg-transparent text-sm outline-none placeholder:text-ink/35" placeholder="Search files, functions, insights…" /><kbd className="text-xs text-ink/35">ESC</kbd></div>
            <div className="p-2">
              <p className="eyebrow px-3 py-2 text-ink/35">Go to</p>
              {navItems.map((item) => { 
                const Icon = icons[item.id]; 
                return (
                  <button 
                    key={item.id} 
                    onClick={() => repoId ? selectView(item.id) : setNewCase(true)} 
                    disabled={!repoId && item.id !== "overview"}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold hover:bg-paper-deep text-left disabled:opacity-40"
                  >
                    <Icon size={17} />
                    <span className="flex-1">{item.label}</span>
                    <span className="text-[10px] text-ink/30">{item.index}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {newCase && (
        <div className="fixed inset-0 z-[80] grid place-items-center bg-ink/45 p-4 backdrop-blur-sm" onMouseDown={() => !isAnalyzing && setNewCase(false)}>
          <div onMouseDown={(e) => e.stopPropagation()} className="relative w-full max-w-2xl overflow-hidden rounded-[28px] border border-ink/20 bg-[#faf8f1] p-6 shadow-2xl sm:p-9">
            {!isAnalyzing && (
              <button onClick={() => setNewCase(false)} className="absolute right-5 top-5 rounded-full border border-ink/15 p-2 hover:bg-ink/5"><X size={18} /></button>
            )}
            <div className="mb-7 grid h-12 w-12 place-items-center rounded-2xl bg-acid shadow-[3px_3px_0_#20241f]"><Sparkles size={21} /></div>
            <p className="eyebrow text-ember">Open a new case</p>
            <h2 className="display mt-2 text-4xl font-bold">What are we dissecting?</h2>
            <p className="mt-2 text-sm text-ink/50 font-medium">Paste a public GitHub repository URL. Python repositories are supported in this release.</p>
            
            <div className="mt-7 flex flex-col gap-3">
              <div className="flex flex-col gap-2 rounded-2xl border border-ink/20 bg-white p-2 focus-within:border-ink sm:flex-row">
                <input 
                  value={url} 
                  onChange={(e) => setUrl(e.target.value)} 
                  placeholder="https://github.com/owner/repository" 
                  disabled={isAnalyzing}
                  className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm outline-none" 
                />
                <button 
                  onClick={triggerAnalysis} 
                  className="flex items-center justify-center gap-2 rounded-xl bg-ember px-5 py-3 text-sm font-bold text-white disabled:opacity-50" 
                  disabled={!url.trim() || isAnalyzing}
                >
                  {isAnalyzing ? (
                    <><span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />Dissecting</>
                  ) : (
                    <><Play size={15} fill="currentColor" />Analyze</>
                  )}
                </button>
              </div>

              <div className="flex items-center gap-3 px-1.5">
                <label className="text-xs font-bold text-ink/50 uppercase tracking-wider">Branch/Ref:</label>
                <input 
                  value={ref}
                  onChange={(e) => setRef(e.target.value)}
                  placeholder="main"
                  disabled={isAnalyzing}
                  className="w-24 bg-transparent border-b border-ink/20 text-xs font-bold text-ink focus:border-ink outline-none"
                />
              </div>
            </div>

            {errorMsg && (
              <div className="mt-4 p-3 bg-ember/10 border border-ember/25 text-ember text-xs font-bold rounded-xl">
                {errorMsg}
              </div>
            )}

            {isAnalyzing && (
              <div className="mt-6">
                <div className="mb-2 flex justify-between text-[10px] font-bold uppercase tracking-[.13em]">
                  <span>{getStageLabel(stage)}</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full border border-ink/15 bg-paper">
                  <div className="h-full bg-gradient-to-r from-ember via-peach to-acid transition-all duration-500" style={{ width: `${progress}%` }} />
                </div>
              </div>
            )}
            
            <div className="mt-7 flex items-center gap-2 text-[11px] text-ink/40"><Clock3 size={14} />Most repositories take 2–5 minutes. You can safely leave this screen.</div>
          </div>
        </div>
      )}

      {settingsOpen && (
        <div className="fixed inset-0 z-[80] grid place-items-center bg-ink/45 p-4 backdrop-blur-sm" onMouseDown={() => setSettingsOpen(false)}>
          <div onMouseDown={(e) => e.stopPropagation()} className="relative w-full max-w-md overflow-hidden rounded-[28px] border border-ink/20 bg-[#faf8f1] p-6 shadow-2xl sm:p-8">
            <button onClick={() => setSettingsOpen(false)} className="absolute right-5 top-5 rounded-full border border-ink/15 p-2 hover:bg-ink/5"><X size={18} /></button>
            <div className="mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-acid shadow-[3px_3px_0_#20241f]"><Settings2 size={21} /></div>
            <p className="eyebrow text-ember">System Configuration</p>
            <h2 className="display mt-1 text-3xl font-bold">Settings</h2>
            
            <div className="mt-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-ink/65 uppercase tracking-wider">Groq API Key</label>
                <input 
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder="gsk_..."
                  className="w-full rounded-xl border border-ink/15 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-ink"
                />
                <p className="text-[10px] text-ink/40">Stored locally in your browser's localStorage. Never sent to third parties except when authenticating requests directly with Groq.</p>
              </div>

              <button 
                onClick={saveSettings}
                className="w-full py-3 bg-ink text-paper font-bold rounded-xl shadow-[3px_3px_0_#20241f] transition hover:-translate-y-0.5 hover:shadow-[4px_4px_0_#20241f]"
              >
                Save configurations
              </button>
            </div>
          </div>
        </div>
      )}

      {infoOpen && (
        <div className="fixed inset-0 z-[80] grid place-items-center bg-ink/45 p-4 backdrop-blur-sm" onMouseDown={() => setInfoOpen(false)}>
          <div onMouseDown={(e) => e.stopPropagation()} className="relative w-full max-w-2xl overflow-hidden rounded-[28px] border border-ink/20 bg-[#faf8f1] p-6 shadow-2xl sm:p-9 max-h-[85vh] overflow-y-auto no-scrollbar">
            <button onClick={() => setInfoOpen(false)} className="absolute right-5 top-5 rounded-full border border-ink/15 p-2 hover:bg-ink/5"><X size={18} /></button>
            <div className="mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-acid shadow-[3px_3px_0_#20241f]"><CircleHelp size={21} /></div>
            <p className="eyebrow text-ember">Technical overview</p>
            <h2 className="display mt-1 text-3xl font-bold mb-4">How CodeAutopsy Works</h2>
            
            <div className="space-y-6 text-sm text-ink/75 leading-relaxed">
              <div>
                <h3 className="font-bold text-ink mb-1">1. Shallow Repository Cloning</h3>
                <p>The orchestrator performs a shallow checkout (`git clone --depth 1`) to checkout your codebase branch immediately without downloading historical Git blobs, respecting size limits.</p>
              </div>
              
              <div>
                <h3 className="font-bold text-ink mb-1">2. AST Syntax Extraction</h3>
                <p>We use Tree-Sitter parser bindings to parse all `.py` files, building an accurate inventory of classes, functions, decorator nodes, and import symbols. Cyclomatic complexity is calculated directly by counting conditional branches inside the AST subtree.</p>
              </div>

              <div>
                <h3 className="font-bold text-ink mb-1">3. Graph Construction</h3>
                <p>Using NetworkX, we model imports as module dependency graphs and find approximate execution call pathways by resolving invoked identifiers to defined function namespaces. Coordinate layouts are generated using spring layouts for React Flow.</p>
              </div>

              <div>
                <h3 className="font-bold text-ink mb-1">4. Semantic Indexing (FAISS)</h3>
                <p>Files are chunked syntactically around class/function definitions. Chunks are embedded using Sentence-Transformers (`all-MiniLM-L6-v2`) and stored in a local, fast CPU flat L2 FAISS vector index.</p>
              </div>

              <div>
                <h3 className="font-bold text-ink mb-1">5. LLM-Authored Documentation & RAG</h3>
                <p>All structured inputs are compiled. Groq LLM parses details to write onboarding guides, architectural boundary maps, and answers natural chat queries, returning source citations matching line intervals.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Simple internal helper icon
function PlusIcon({ size, className }: { size: number; className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </svg>
  );
}
