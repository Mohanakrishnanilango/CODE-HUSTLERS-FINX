import React from 'react';
import { Waves, Radio, ShieldCheck } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="border-b border-marine-800 bg-marine-900/90 backdrop-blur-md px-6 py-4 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="relative flex items-center justify-center w-12 h-12 rounded-xl bg-marine-800 border border-marine-700 shadow-inner">
            <Waves className="w-7 h-7 text-sonar-cyan" />
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-sonar-green rounded-full animate-ping opacity-75" />
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-sonar-green rounded-full" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono font-bold tracking-widest text-xs px-2 py-0.5 rounded bg-sonar-cyan/10 text-sonar-cyan border border-sonar-cyan/30">
                SIH26057
              </span>
              <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                <Radio className="w-3 h-3 text-sonar-green animate-pulse" /> SSS Analysis
              </span>
            </div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Marine Sonar Intelligence
              <span className="text-xs font-normal text-slate-400 hidden sm:inline">
                | Underwater Debris & Anomaly Detection
              </span>
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-marine-800/80 border border-marine-700 text-xs font-mono">
            <span className="w-2.5 h-2.5 rounded-full bg-sonar-green animate-pulse"></span>
            <span className="text-slate-300 font-medium">System Ready</span>
          </div>

          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-marine-800/50 border border-marine-700/60 text-xs text-slate-400">
            <ShieldCheck className="w-4 h-4 text-sonar-cyan" />
            <span>Detector: <strong className="text-slate-200">SyntheticDetector</strong> (Modular Interface)</span>
          </div>
        </div>
      </div>
    </header>
  );
};
