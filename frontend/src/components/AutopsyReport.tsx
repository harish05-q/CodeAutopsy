"use client";

import React, { useEffect, useState } from 'react';
import { getArtifact } from '@/lib/api';

interface AutopsyReportProps {
  analysisId: number;
}

interface AutopsyData {
  executive_summary: string;
  architecture_pattern: string;
  key_components: Array<{
    name: string;
    description: string;
    responsibilities: string[];
  }>;
  design_anti_patterns: string[];
  quality_score: number;
  actionable_recommendations: string[];
}

export default function AutopsyReport({ analysisId }: AutopsyReportProps) {
  const [report, setReport] = useState<AutopsyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getArtifact<AutopsyData>(analysisId, 'autopsy_report')
      .then((data) => {
        setReport(data);
      })
      .catch((err) => {
        // Artifact might not exist if LLM failed or API key missing
        setError(err instanceof Error ? err.message : 'Report not available');
      })
      .finally(() => setLoading(false));
  }, [analysisId]);

  if (loading) return null; // Don't show anything while checking
  if (error || !report) {
    return (
      <div className="glass-card p-6 border border-amber-200 bg-amber-50 mb-6">
        <div className="flex gap-3">
          <span className="text-xl">🤖</span>
          <div>
            <h3 className="font-bold text-amber-900">LLM Architectural Autopsy Not Available</h3>
            <p className="text-sm text-amber-800 mt-1">
              To view the AI-generated autopsy report, ensure your <code>CODEAUTOPSY_GROQ_API_KEY</code> is set in the <code>.env</code> file.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card mb-8 overflow-hidden bg-gradient-to-br from-indigo-900 to-purple-900 text-white shadow-2xl">
      <div className="p-8">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
              <span>🧠</span> Architectural Autopsy
            </h2>
            <p className="text-indigo-200 mt-1">AI-synthesized codebase analysis</p>
          </div>
          <div className="text-center">
            <div className="text-4xl font-black text-emerald-400">{report.quality_score}</div>
            <div className="text-xs uppercase tracking-widest text-indigo-300 font-bold mt-1">Quality Score</div>
          </div>
        </div>

        <div className="bg-white/10 backdrop-blur-md rounded-xl p-6 border border-white/20 mb-6">
          <h3 className="text-sm font-bold uppercase tracking-widest text-indigo-300 mb-2">Executive Summary</h3>
          <p className="text-indigo-50 leading-relaxed">{report.executive_summary}</p>
        </div>

        <div className="bg-white/10 backdrop-blur-md rounded-xl p-6 border border-white/20 mb-6">
          <h3 className="text-sm font-bold uppercase tracking-widest text-indigo-300 mb-2">Primary Pattern</h3>
          <p className="text-xl font-bold text-white">{report.architecture_pattern}</p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mb-6">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-indigo-300 mb-4">Key Components</h3>
            <div className="space-y-4">
              {report.key_components.map((comp, i) => (
                <div key={i} className="bg-black/20 rounded-lg p-4 border border-white/10">
                  <h4 className="font-bold text-indigo-100">{comp.name}</h4>
                  <p className="text-sm text-indigo-200 mt-1 mb-2">{comp.description}</p>
                  <ul className="list-disc pl-4 text-xs text-indigo-300 space-y-1">
                    {comp.responsibilities.map((r, j) => <li key={j}>{r}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-rose-300 mb-4">Anti-Patterns & Risks</h3>
            <div className="bg-rose-900/30 rounded-lg p-4 border border-rose-500/30 mb-6">
              <ul className="list-disc pl-4 text-sm text-rose-200 space-y-2">
                {report.design_anti_patterns.length > 0 
                  ? report.design_anti_patterns.map((p, i) => <li key={i}>{p}</li>)
                  : <li>No structural anti-patterns detected.</li>
                }
              </ul>
            </div>

            <h3 className="text-sm font-bold uppercase tracking-widest text-emerald-300 mb-4">Recommendations</h3>
            <div className="bg-emerald-900/30 rounded-lg p-4 border border-emerald-500/30">
              <ul className="list-disc pl-4 text-sm text-emerald-200 space-y-2">
                {report.actionable_recommendations.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
