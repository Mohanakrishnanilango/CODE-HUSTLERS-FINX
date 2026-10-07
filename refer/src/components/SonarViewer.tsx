import React, { useState } from 'react';
import { SonarPingRecord } from '../types/sonar';
import { DetectionResult } from '../types/detection';
import { CLASS_FORMATTERS, formatTargetClass } from '../services/detectionService';
import { Sliders, ShieldAlert, Compass } from 'lucide-react';

interface SonarViewerProps {
  pings: SonarPingRecord[];
  selectedPingId: number;
  onSelectPing: (pingId: number) => void;
  detection: DetectionResult | null;
}

export const SonarViewer: React.FC<SonarViewerProps> = ({
  pings,
  selectedPingId,
  onSelectPing,
  detection
}) => {
  const [filterMode, setFilterMode] = useState<string>('raw');
  const selectedPing = pings.find(p => p.ping_id === selectedPingId) || pings[0];

  if (!selectedPing) {
    return (
      <div className="bg-marine-900 border border-marine-800 rounded-xl p-8 text-center text-slate-400">
        No sonar record selected. Upload a log to view acoustic imagery.
      </div>
    );
  }

  // Bounding box calculation relative to 640x640 image
  const bbox = detection ? detection.bbox : selectedPing.bbox;
  const [bx, by, bw, bh] = bbox;
  // Convert 640px base to percentages for responsive SVG overlay
  const leftPct = (bx / 640) * 100;
  const topPct = (by / 640) * 100;
  const widthPct = (bw / 640) * 100;
  const heightPct = (bh / 640) * 100;

  const targetClass = detection?.object_class || selectedPing.target_class;
  const confidence = detection?.confidence ?? selectedPing.confidence;
  const formatter = CLASS_FORMATTERS[targetClass.toLowerCase()] || {
    label: formatTargetClass(targetClass),
    color: '#00F0FF',
    badgeClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
  };

  return (
    <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg space-y-4">
      {/* Viewer Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-marine-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-sonar-cyan animate-pulse"></span>
            Side-Scan Sonar Imagery
          </h2>
          <p className="text-xs text-slate-400">
            Acoustic waterfall backscatter | Record: <span className="font-mono text-slate-200">Ping {String(selectedPing.ping_id).padStart(4, '0')}</span>
          </p>
        </div>

        {/* Filter / Preprocessing mode selector (Modular interface stub) */}
        <div className="flex items-center gap-2">
          <Sliders className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-xs text-slate-400">Filter:</span>
          <select
            value={filterMode}
            onChange={(e) => setFilterMode(e.target.value)}
            className="bg-marine-800 border border-marine-700 text-slate-200 text-xs rounded px-2 py-1 outline-none font-mono"
          >
            <option value="raw">Raw Acoustic</option>
            <option value="lee">Lee Filter (Speckle)</option>
            <option value="clahe">CLAHE Contrast</option>
          </select>
        </div>
      </div>

      {/* Ping Record Navigation Selector */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-marine-800/60">
        <span className="text-xs font-mono text-slate-400 shrink-0 uppercase tracking-wide">Pings:</span>
        <div className="flex gap-2">
          {pings.map((p) => {
            const isSelected = p.ping_id === selectedPingId;
            const pClass = CLASS_FORMATTERS[p.target_class]?.label || p.target_class;
            return (
              <button
                key={p.ping_id}
                onClick={() => onSelectPing(p.ping_id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all flex items-center gap-1.5 shrink-0 ${
                  isSelected
                    ? 'bg-sonar-cyan text-marine-950 font-bold shadow-sonar-cyan'
                    : 'bg-marine-800 text-slate-300 hover:bg-marine-700 hover:text-white border border-marine-700'
                }`}
              >
                <span>Ping {String(p.ping_id).padStart(4, '0')}</span>
                <span className={`text-[10px] px-1 py-0.2 rounded ${isSelected ? 'bg-black/20 text-marine-950' : 'text-slate-400'}`}>
                  {pClass}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Acoustic Waterfall Imagery Container */}
      <div className="relative aspect-square max-w-2xl mx-auto rounded-lg overflow-hidden border border-marine-700 bg-black flex items-center justify-center">
        {/* Sonar Waterfall Image */}
        <img
          src={selectedPing.image}
          alt={`Sonar ping ${selectedPing.ping_id}`}
          className={`w-full h-full object-contain ${filterMode === 'clahe' ? 'contrast-125 brightness-110' : ''}`}
        />

        {/* Sonar Scanline Grid Overlay */}
        <div className="absolute inset-0 pointer-events-none opacity-20 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.5)_50%)] bg-[length:100%_4px]" />

        {/* Detection Bounding Box Overlay */}
        <div
          className="absolute border-2 transition-all duration-300 pointer-events-none shadow-lg"
          style={{
            borderColor: formatter.color,
            boxShadow: `0 0 12px ${formatter.color}66`,
            left: `${leftPct}%`,
            top: `${topPct}%`,
            width: `${widthPct}%`,
            height: `${heightPct}%`
          }}
        >
          {/* Target Corner Reticles */}
          <div className="absolute -top-1.5 -left-1.5 w-3 h-3 border-t-2 border-l-2" style={{ borderColor: formatter.color }} />
          <div className="absolute -top-1.5 -right-1.5 w-3 h-3 border-t-2 border-r-2" style={{ borderColor: formatter.color }} />
          <div className="absolute -bottom-1.5 -left-1.5 w-3 h-3 border-b-2 border-l-2" style={{ borderColor: formatter.color }} />
          <div className="absolute -bottom-1.5 -right-1.5 w-3 h-3 border-b-2 border-r-2" style={{ borderColor: formatter.color }} />

          {/* Floating Tag inside/above bounding box */}
          <div
            className="absolute -top-6 left-0 px-2 py-0.5 text-[11px] font-mono font-bold tracking-tight rounded whitespace-nowrap text-marine-950 flex items-center gap-1 shadow-md"
            style={{ backgroundColor: formatter.color }}
          >
            <span>{formatter.label}</span>
            <span>{Math.round(confidence * 100)}%</span>
          </div>
        </div>

        {/* Crosshair / Navigation Indicators */}
        <div className="absolute top-3 left-3 bg-marine-950/80 backdrop-blur border border-marine-700/80 rounded px-2.5 py-1 text-[11px] font-mono text-slate-300 flex items-center gap-2">
          <Compass className="w-3.5 h-3.5 text-sonar-cyan" />
          <span>HDG: {selectedPing.heading.toFixed(1)}°</span>
          <span className="text-slate-500">|</span>
          <span>ALT: {selectedPing.altitude.toFixed(1)}m</span>
          <span className="text-slate-500">|</span>
          <span className="uppercase text-sonar-green">{selectedPing.side}</span>
        </div>

        <div className="absolute bottom-3 right-3 bg-marine-950/80 backdrop-blur border border-marine-700/80 rounded px-2.5 py-1 text-[10px] font-mono text-amber-300 flex items-center gap-1.5">
          <ShieldAlert className="w-3 h-3 text-amber-400" />
          <span>Synthetic Detection</span>
        </div>
      </div>

      {/* Detection Info Panel */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 rounded-lg bg-marine-950/70 border border-marine-800 font-mono text-xs">
        <div>
          <span className="text-slate-400 block text-[11px]">Object:</span>
          <span className="font-bold text-white text-sm" style={{ color: formatter.color }}>
            {formatter.label}
          </span>
        </div>

        <div>
          <span className="text-slate-400 block text-[11px]">Confidence:</span>
          <span className="font-bold text-white text-sm text-sonar-green">
            {Math.round(confidence * 100)}%
          </span>
        </div>

        <div>
          <span className="text-slate-400 block text-[11px]">Channel:</span>
          <span className="font-medium text-slate-200 capitalize">
            {selectedPing.side} ({selectedPing.sonar_range}m range)
          </span>
        </div>

        <div>
          <span className="text-slate-400 block text-[11px]">Bounding Box:</span>
          <span className="text-slate-300 text-[11px]">
            [{bx}, {by}, {bw}, {bh}]
          </span>
        </div>
      </div>
    </div>
  );
};
