import React from 'react';
import { UploadCloud, BarChart3, Crosshair, MapPin, FileDown } from 'lucide-react';

interface SidebarProps {
  activeSection: string;
  onSelectSection: (section: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeSection, onSelectSection }) => {
  const navItems = [
    { id: 'upload', label: '1. Upload Sonar Log', icon: UploadCloud },
    { id: 'overview', label: '2. Survey Overview', icon: BarChart3 },
    { id: 'detections', label: '3. Detections', icon: Crosshair },
    { id: 'map', label: '4. Map', icon: MapPin },
    { id: 'reports', label: '5. Reports', icon: FileDown },
  ];

  return (
    <aside className="w-full md:w-64 bg-marine-900 border-r border-marine-800 p-4 shrink-0 flex flex-col justify-between">
      <div className="space-y-6">
        <div>
          <h2 className="text-xs font-mono uppercase tracking-wider text-slate-400 px-3 mb-2 font-semibold">
            Workflow Navigation
          </h2>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectSection(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-sonar-cyan/15 text-sonar-cyan border border-sonar-cyan/30 shadow-sonar-cyan/20'
                      : 'text-slate-300 hover:bg-marine-800 hover:text-white'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-sonar-cyan' : 'text-slate-400'}`} />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="p-3 rounded-lg bg-marine-950/60 border border-marine-800 text-xs text-slate-400 space-y-2">
          <div className="font-mono text-slate-300 font-medium flex items-center justify-between">
            <span>Detection Pipeline</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300">Phase 1 MVP</span>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-400">
            Detector: <strong className="text-slate-200">SyntheticDetector</strong>. Prepared for High-Precision Detection integration.
          </p>
        </div>
      </div>

      <div className="pt-4 border-t border-marine-800 text-[11px] text-slate-500 font-mono">
        SIH 2024-2026 Problem SIH26057
      </div>
    </aside>
  );
};
