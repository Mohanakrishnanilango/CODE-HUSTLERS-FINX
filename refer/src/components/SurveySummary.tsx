import React from 'react';
import { DetectionResult } from '../types/detection';
import { CLASS_FORMATTERS } from '../services/detectionService';
import { BarChart3, Percent, CheckCircle, Database } from 'lucide-react';

interface SurveySummaryProps {
  totalRecords: number;
  detections: DetectionResult[];
}

export const SurveySummary: React.FC<SurveySummaryProps> = ({
  totalRecords,
  detections
}) => {
  // Dynamically calculate class counts
  const countsByClass = detections.reduce((acc, d) => {
    const cls = d.object_class.toLowerCase();
    acc[cls] = (acc[cls] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Dynamically calculate average confidence
  const avgConfidence = detections.length > 0
    ? detections.reduce((sum, d) => sum + d.confidence, 0) / detections.length
    : 0;

  // Expected classes to show
  const classesToShow = [
    { key: 'ghost_net', label: 'Ghost Nets', color: CLASS_FORMATTERS['ghost_net'].color },
    { key: 'fishing_gear', label: 'Fishing Gear', color: CLASS_FORMATTERS['fishing_gear'].color },
    { key: 'pipeline', label: 'Pipelines', color: CLASS_FORMATTERS['pipeline'].color },
    { key: 'shipwreck', label: 'Shipwrecks', color: CLASS_FORMATTERS['shipwreck'].color },
    { key: 'mine_cylinder', label: 'Mine Cylinders', color: CLASS_FORMATTERS['mine_cylinder'].color },
  ];

  return (
    <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-marine-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-sonar-cyan" />
            Survey Overview & Analytics
          </h2>
          <p className="text-xs text-slate-400">
            Real-time dynamically calculated debris & anomaly metrics
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
          <span className="w-2 h-2 rounded-full bg-sonar-green animate-pulse"></span>
          <span>Dynamic Aggregation</span>
        </div>
      </div>

      {/* Main KPI Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono">
        <div className="p-3.5 rounded-lg bg-marine-950/80 border border-marine-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Total Sonar Records</span>
            <Database className="w-3.5 h-3.5 text-sonar-cyan" />
          </div>
          <div className="text-2xl font-bold text-white">{totalRecords}</div>
          <span className="text-[10px] text-slate-500">Pings processed</span>
        </div>

        <div className="p-3.5 rounded-lg bg-marine-950/80 border border-marine-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Total Detections</span>
            <CheckCircle className="w-3.5 h-3.5 text-sonar-green" />
          </div>
          <div className="text-2xl font-bold text-sonar-green">{detections.length}</div>
          <span className="text-[10px] text-slate-500">Verified anomalies</span>
        </div>

        <div className="p-3.5 rounded-lg bg-marine-950/80 border border-marine-800 col-span-2">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Average Confidence</span>
            <Percent className="w-3.5 h-3.5 text-sonar-cyan" />
          </div>
          <div className="text-2xl font-bold text-sonar-cyan">
            {detections.length > 0 ? `${(avgConfidence * 100).toFixed(1)}%` : '0%'}
          </div>
          <span className="text-[10px] text-slate-500">Calculated across all detection classes</span>
        </div>
      </div>

      {/* Target Breakdown Grid */}
      <div className="pt-2">
        <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2 font-semibold">
          Classification Breakdown
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 font-mono text-xs">
          {classesToShow.map((item) => {
            const count = countsByClass[item.key] || 0;
            return (
              <div
                key={item.key}
                className="p-3 rounded-lg bg-marine-950/50 border border-marine-800/80 flex flex-col justify-between"
              >
                <div className="flex items-center gap-1.5 text-slate-300 text-[11px] mb-1">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                  <span className="truncate">{item.label}</span>
                </div>
                <div className="text-xl font-bold" style={{ color: item.color }}>
                  {count}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
