"use client";

import React, { useEffect, useState } from 'react';
import { getArtifact, RiskFinding } from '@/lib/api';

interface RiskDashboardProps {
  analysisId: number;
}

export default function RiskDashboard({ analysisId }: RiskDashboardProps) {
  const [risks, setRisks] = useState<RiskFinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getArtifact<RiskFinding[]>(analysisId, 'all_findings')
      .then((data) => {
        setRisks(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load risks');
      })
      .finally(() => setLoading(false));
  }, [analysisId]);

  if (loading) return <div className="p-4 text-gray-500">Loading risk findings...</div>;
  if (error) return <div className="p-4 text-red-500">{error}</div>;

  if (risks.length === 0) {
    return (
      <div className="glass-card p-6 text-center text-gray-500">
        <span className="text-4xl mb-2 block">🎉</span>
        <h3 className="font-bold text-lg text-gray-800">No Risks Detected!</h3>
        <p>The codebase looks exceptionally clean based on our analysis rules.</p>
      </div>
    );
  }

  // Group by severity
  const counts = {
    critical: risks.filter(r => r.severity === 'critical').length,
    high: risks.filter(r => r.severity === 'high').length,
    medium: risks.filter(r => r.severity === 'medium').length,
    low: risks.filter(r => r.severity === 'low').length,
  };

  return (
    <div className="glass-card overflow-hidden">
      <div className="bg-white px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-800">Risk Assessment</h2>
        <div className="flex gap-3">
          {counts.critical > 0 && <span className="px-2 py-1 rounded-full bg-red-100 text-red-800 text-xs font-bold">{counts.critical} Critical</span>}
          {counts.high > 0 && <span className="px-2 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-bold">{counts.high} High</span>}
          {counts.medium > 0 && <span className="px-2 py-1 rounded-full bg-yellow-100 text-yellow-800 text-xs font-bold">{counts.medium} Medium</span>}
          {counts.low > 0 && <span className="px-2 py-1 rounded-full bg-blue-100 text-blue-800 text-xs font-bold">{counts.low} Low</span>}
        </div>
      </div>
      <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
        {risks.map((risk, i) => {
          let badgeColor = 'bg-gray-100 text-gray-800';
          if (risk.severity === 'critical') badgeColor = 'bg-red-100 text-red-800';
          if (risk.severity === 'high') badgeColor = 'bg-orange-100 text-orange-800';
          if (risk.severity === 'medium') badgeColor = 'bg-yellow-100 text-yellow-800';
          if (risk.severity === 'low') badgeColor = 'bg-blue-100 text-blue-800';

          return (
            <div key={i} className="p-4 hover:bg-gray-50 transition-colors">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${badgeColor}`}>
                      {risk.severity}
                    </span>
                    <span className="text-sm font-semibold text-gray-700 uppercase">{risk.category.replace(/_/g, ' ')}</span>
                  </div>
                  <h4 className="font-bold text-gray-900 mb-1">{risk.title}</h4>
                  <p className="text-sm text-gray-600 mb-2">{risk.description}</p>
                </div>
              </div>
              
              <div className="text-xs text-gray-500 font-mono bg-gray-100 p-2 rounded">
                File: {risk.file_path} {risk.line_number && `(Line ${risk.line_number})`}
              </div>
              
              {risk.suggestion && (
                <div className="mt-2 text-sm text-emerald-700 bg-emerald-50 p-2 rounded border border-emerald-100 flex gap-2">
                  <span>💡</span>
                  <span>{risk.suggestion}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
