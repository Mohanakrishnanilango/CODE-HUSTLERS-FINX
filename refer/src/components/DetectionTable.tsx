import React from 'react';
import { DetectionResult } from '../types/detection';
import { CLASS_FORMATTERS } from '../services/detectionService';
import { Crosshair, Check, ExternalLink } from 'lucide-react';

interface DetectionTableProps {
  detections: DetectionResult[];
  selectedDetectionId: string | null;
  onSelectDetection: (detectionId: string, pingId: number) => void;
}

export const DetectionTable: React.FC<DetectionTableProps> = ({
  detections,
  selectedDetectionId,
  onSelectDetection
}) => {
  const formatTimeOnly = (isoString: string): string => {
    try {
      const match = isoString.match(/T(\d{2}:\d{2}:\d{2})/);
      return match ? match[1] : isoString;
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-marine-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Crosshair className="w-5 h-5 text-sonar-cyan" />
            Detection Register
          </h2>
          <p className="text-xs text-slate-400">
            Automated anomaly extractions from side-scan sonar log
          </p>
        </div>

        <div className="text-xs font-mono text-slate-400">
          Click any row to synchronize <span className="text-sonar-cyan">Map</span> + <span className="text-sonar-cyan">Sonar Imagery</span>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-marine-800">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-marine-950/90 text-slate-400 border-b border-marine-800 uppercase tracking-wider text-[11px]">
            <tr>
              <th className="py-3 px-4 font-semibold">Object</th>
              <th className="py-3 px-4 font-semibold">Confidence</th>
              <th className="py-3 px-4 font-semibold">Latitude</th>
              <th className="py-3 px-4 font-semibold">Longitude</th>
              <th className="py-3 px-4 font-semibold">Timestamp</th>
              <th className="py-3 px-4 font-semibold">Ping</th>
              <th className="py-3 px-4 font-semibold text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-marine-800/60">
            {detections.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-500">
                  No detections available. Please upload a sonar survey log.
                </td>
              </tr>
            ) : (
              detections.map((det) => {
                const isSelected = det.id === selectedDetectionId;
                const formatter = CLASS_FORMATTERS[det.object_class.toLowerCase()] || {
                  label: det.display_name,
                  color: '#00F0FF',
                  badgeClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                };

                return (
                  <tr
                    key={det.id}
                    onClick={() => onSelectDetection(det.id, det.ping_id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-sonar-cyan/15 border-l-4 border-l-sonar-cyan font-medium text-white'
                        : 'hover:bg-marine-800/60 text-slate-300'
                    }`}
                  >
                    <td className="py-3.5 px-4 font-sans font-semibold flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: formatter.color }} />
                      <span style={{ color: isSelected ? '#FFFFFF' : formatter.color }}>
                        {formatter.label}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 font-bold text-sonar-green">
                      {Math.round(det.confidence * 100)}%
                    </td>

                    <td className="py-3.5 px-4 text-slate-300">
                      {det.latitude.toFixed(6)}
                    </td>

                    <td className="py-3.5 px-4 text-slate-300">
                      {det.longitude.toFixed(6)}
                    </td>

                    <td className="py-3.5 px-4 text-slate-400">
                      {formatTimeOnly(det.timestamp)}
                    </td>

                    <td className="py-3.5 px-4 text-sonar-cyan font-bold">
                      {String(det.ping_id).padStart(4, '0')}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      {isSelected ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-sonar-cyan/20 text-sonar-cyan font-medium">
                          <Check className="w-3 h-3" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] text-slate-500 group-hover:text-slate-300">
                          Select <ExternalLink className="w-2.5 h-2.5" />
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
