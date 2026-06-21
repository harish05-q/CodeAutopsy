"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Background, Controls, Edge, Handle, MarkerType, MiniMap, Node, NodeProps, Position, ReactFlow } from "@xyflow/react";
import { Braces, ChevronDown, Crosshair, Maximize2, Search, Share2 } from "lucide-react";
import { fetchDependencyGraph, fetchCallGraph, type GraphNode, type GraphEdge } from "../api-client";

type ModuleData = { label: string; kind: string; files: number; tone: string };

function ModuleNode({ data, selected }: NodeProps<Node<ModuleData>>) {
  return (
    <div className={`min-w-[150px] rounded-2xl border-2 bg-[#faf8f1] p-3 shadow-[3px_3px_0_rgba(32,36,31,.16)] transition ${selected ? "scale-105 border-ember" : "border-ink/20"}`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-ink" />
      <div className="mb-3 flex items-center justify-between">
        <span className="grid h-7 w-7 place-items-center rounded-lg" style={{ background: data.tone }}>
          <Braces size={14} />
        </span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-ink/35">{data.kind}</span>
      </div>
      <div className="font-mono text-xs font-bold break-all">{data.label}</div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-ink" />
    </div>
  );
}

const nodeTypes = { module: ModuleNode };

interface GraphViewProps {
  kind: "dependencies" | "calls";
  repoId: string;
}

export function GraphView({ kind, repoId }: GraphViewProps) {
  const [nodes, setNodes] = useState<Node<ModuleData>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  const isCalls = kind === "calls";

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMsg("");
    
    async function loadGraph() {
      try {
        const fetchMethod = isCalls ? fetchCallGraph : fetchDependencyGraph;
        const data = await fetchMethod(repoId);
        
        if (active) {
          // Format nodes and edges to xyflow ReactFlow structure
          const formattedNodes: Node<ModuleData>[] = data.nodes.map(n => ({
            id: n.id,
            type: "module",
            position: n.position,
            data: {
              label: n.data.label,
              kind: n.data.kind,
              files: n.data.files || 1,
              tone: n.data.tone || "#f4b183"
            }
          }));

          const formattedEdges: Edge[] = data.edges.map(e => ({
            id: e.id,
            source: e.source,
            target: e.target,
            animated: e.animated,
            style: e.style,
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: e.markerEnd?.color || "#5f685e"
            }
          }));

          setNodes(formattedNodes);
          setEdges(formattedEdges);
          
          if (formattedNodes.length > 0) {
            setSelected(formattedNodes[0].id);
          } else {
            setSelected("");
          }
          setLoading(false);
        }
      } catch (err: any) {
        if (active) {
          setErrorMsg(err.message || "Failed to load graph data.");
          setLoading(false);
        }
      }
    }

    loadGraph();
    return () => { active = false; };
  }, [kind, repoId, isCalls]);

  const selectedNode = useMemo(() => nodes.find((node) => node.id === selected), [nodes, selected]);

  // Compute graph properties for selection side panel
  const incomingCount = useMemo(() => edges.filter(e => e.target === selected).length, [edges, selected]);
  const outgoingCount = useMemo(() => edges.filter(e => e.source === selected).length, [edges, selected]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => setSelected(node.id), []);

  const filteredNodes = useMemo(() => {
    if (!query.trim()) return nodes;
    return nodes.map(node => ({
      ...node,
      hidden: !node.data.label.toLowerCase().includes(query.toLowerCase())
    }));
  }, [nodes, query]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <span className="h-8 w-8 animate-spin rounded-full border-4 border-ink/15 border-t-ember" />
        <span className="text-sm font-bold text-ink/50 uppercase tracking-widest">Constructing {kind} canvas...</span>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center max-w-md mx-auto">
        <div className="text-ember font-bold mb-2">Error building graph relations</div>
        <p className="text-xs text-ink/50 leading-5">{errorMsg}</p>
      </div>
    );
  }

  return (
    <section>
      <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="eyebrow text-ember">Interactive specimen</p>
          <h1 className="display mt-2 text-4xl font-bold sm:text-5xl">{isCalls ? "Call anatomy" : "Dependency map"}</h1>
          <p className="mt-2 max-w-2xl text-sm text-ink/55 leading-6">
            {isCalls 
              ? "Follow execution flows and call paths parsed directly from AST function invocations." 
              : "Trace package imports and module-to-module relations. Highlight nodes to trace connections."}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 rounded-xl border border-ink/15 bg-white/60 px-4 py-2.5 text-xs font-bold hover:bg-white"><Share2 size={15} />Export</button>
          <button className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-paper"><Maximize2 size={16} /></button>
        </div>
      </div>
      
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-ink/10 p-3">
          <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-xl border border-ink/15 bg-white/60 px-3 py-2">
            <Search size={15} className="text-ink/35" />
            <input 
              value={query} 
              onChange={(e) => setQuery(e.target.value)} 
              className="w-full bg-transparent text-xs outline-none" 
              placeholder={`Find a ${isCalls ? "function" : "module"}…`} 
            />
          </div>
          <button className="flex items-center gap-2 rounded-xl border border-ink/15 px-3 py-2 text-xs font-bold">All layers <ChevronDown size={14} /></button>
          <span className="ml-auto hidden items-center gap-2 pr-2 text-[10px] font-bold uppercase tracking-widest text-ink/35 sm:flex">
            <span className="h-2 w-2 rounded-full bg-ember" />{nodes.length} nodes 
            <span className="ml-2 h-2 w-2 rounded-full bg-mint" />{edges.length} links
          </span>
        </div>

        <div className="grid min-h-[590px] lg:grid-cols-[1fr_280px]">
          <div className="relative min-h-[480px] border-b border-ink/10 lg:border-b-0 lg:border-r">
            {nodes.length > 0 ? (
              <ReactFlow 
                nodes={filteredNodes} 
                edges={edges} 
                nodeTypes={nodeTypes} 
                onNodeClick={onNodeClick} 
                fitView 
                fitViewOptions={{ padding: 0.18 }} 
                minZoom={0.25} 
                maxZoom={1.8}
              >
                <Background color="#a8a99f" gap={28} size={1} />
                <Controls showInteractive={false} />
                <MiniMap nodeColor={(node) => (node.data as ModuleData).tone} maskColor="rgba(244,241,232,.7)" />
              </ReactFlow>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-ink/40 font-bold uppercase tracking-widest">No graph nodes generated.</div>
            )}
            <div className="pointer-events-none absolute left-4 top-4 rounded-lg border border-ink/10 bg-paper/85 px-3 py-2 text-[10px] font-semibold text-ink/50 backdrop-blur">
              <Crosshair size={12} className="mr-1 inline" />Drag to pan · scroll to zoom
            </div>
          </div>
          <aside className="bg-[#eee9dc] p-5 flex flex-col justify-between">
            <div>
              <p className="eyebrow text-ember">Selected {isCalls ? "function" : "module"}</p>
              <h2 className="mt-3 break-all font-mono text-sm font-black">{selectedNode?.data.label ?? "Select a node"}</h2>
              {selectedNode && (
                <span className="mt-3 inline-block rounded-full bg-acid px-2.5 py-1 text-[9px] font-black uppercase tracking-widest">{selectedNode.data.kind}</span>
              )}
              <div className="mt-7 space-y-5">
                {[
                  [isCalls ? "Called by" : "Incoming references", incomingCount], 
                  [isCalls ? "Invokes" : "Outgoing dependencies", outgoingCount], 
                  ["Structure risk", selectedNode ? "Stable" : "N/A"]
                ].map(([label, value]) => (
                  <div key={label as string} className="border-b border-ink/10 pb-3">
                    <div className="eyebrow text-ink/35">{label as string}</div>
                    <div className="display mt-1 text-2xl font-bold">{value}</div>
                  </div>
                ))}
              </div>
            </div>
            <button className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 py-3 text-xs font-bold text-paper hover:bg-ember">
              Open code segment
            </button>
          </aside>
        </div>
      </div>
    </section>
  );
}
