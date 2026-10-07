import React from 'react';
import { DetectionResult } from '../types/detection';
import { CLASS_FORMATTERS } from '../services/detectionService';
import { GeolocationService } from '../services/geolocationService';
import { Compass, Gauge, Radio, MapPin, Layers, Target, Info } from 'lucide-react';

interface DetectionDetailsProps {
  detection: DetectionResult | null;
}

export const DetectionDetails: React.FC<DetectionDetailsProps> = ({ detection }) => {
  if (!detection) {
    return (
      <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg text-center text-slate-400 font-mono text-xs">
        Select a detection from the map or table to inspect telemetry details.
      </div>
    );
  }

  const formatter = CLASS_FORMATTERS[detection.object_class.toLowerCase()] || {
    label: detection.display_name,
    color: '#00F0FF',
    badgeClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
  };

  // Compute future Phase 2 estimated raytraced seabed target position
  const raytracedEstimate = GeolocationService.computeTrueSeabedTargetLocation({
    gps_latitude: detection.latitude,
    gps_longitude: detection.longitude,
    heading_deg: detection.heading_deg,
    altitude_m: detection.altitude_m,
    sonar_range_m: detection.range_m,
    side: detection.side
  });

  return (
    <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-marine-800">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-sonar-cyan" />
          <h2 className="text-lg font-bold text-white">Detection Telemetry</h2>
        </div>
        <span className="font-mono text-xs px-2.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
          Synthetic Detection
        </span>
      </div>

      {/* Target Class Header Banner */}
      <div className="p-4 rounded-lg bg-marine-950/80 border border-marine-800 flex items-center justify-between">
        <div>
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wide block">Detected Target</span>
          <span className="text-xl font-bold font-sans" style={{ color: formatter.color }}>
            {formatter.label}
          </span>
        </div>

        <div className="text-right">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wide block">Confidence</span>
          <span className="text-xl font-bold font-mono text-sonar-green">
            {Math.round(detection.confidence * 100)}%
          </span>
        </div>
      </div>

      {/* Telemetry Grid */}
      <div className="grid grid-cols-2 gap-2.5 font-mono text-xs">
        <div className="p-3 rounded-lg bg-marine-950/60 border border-marine-800/80">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
            <MapPin className="w-3.5 h-3.5 text-sonar-cyan" />
            <span>Latitude</span>
          </div>
          <span className="text-slate-100 font-semibold">{detection.latitude.toFixed(6)}° N</span>
        </div>

        <div className="p-3 rounded-lg bg-marine-950/60 border border-marine-800/80">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
            <MapPin className="w-3.5 h-3.5 text-sonar-cyan" />
            <span>Longitude</span>
          </div>
          <span className="text-slate-100 font-semibold">{detection.longitude.toFixed(6)}° E</span>
        </div>

        <div className="p-3 rounded-lg bg-marine-950/60 border border-marine-800/80">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
            <Compass className="w-3.5 h-3.5 text-sonar-cyan" />
            <span>Towfish Heading</span>
          </div>
          <span className="text-slate-100 font-semibold">{detection.heading_deg.toFixed(1)}°</span>
        </div>

        <div className="p-3 rounded-lg bg-marine-950/60 border border-marine-800/80">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
            <Gauge className="w-3.5 h-3.5 text-sonar-cyan" />
            <span>Altitude (Seabed)</span>
          </div>
          <span className="text-slate-100 font-semibold">{detection.altitude_m.toFixed(1)} m</span>
        </div>

        <div className="p-3 rounded-lg bg-marine-950/60 border border-marine-800/80">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
            <Radio className="w-3.5 h-3.5 text-sonar-cyan" />
            <span>Sonar Slant Range</span>
          </div>
          <span className="text-slate-100 font-semibold">{detection.range_m.toFixed(0)} m</span>
        </div>

        <div className="p-3 rounded-lg bg-marine-950/60 border border-marine-800/80">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
            <Layers className="w-3.5 h-3.5 text-sonar-cyan" />
            <span>Transducer Channel</span>
          </div>
          <span className="text-slate-100 font-semibold uppercase">{detection.side}</span>
        </div>
      </div>

      {/* Geolocation Disclaimer Notice (Required by Section 10) */}
      <div className="p-3 rounded-lg bg-marine-950/80 border border-marine-800 text-[11px] font-mono space-y-2">
        <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
          <Info className="w-3.5 h-3.5 text-sonar-cyan shrink-0" />
          <span>Positioning Reference:</span>
        </div>
        <p className="text-slate-400 italic">
          “{detection.position_label}”
        </p>

        {/* Phase 2 Architecture Projection Info */}
        <div className="pt-2 border-t border-marine-800/80 text-[10px] text-slate-400">
          <span className="text-slate-300 font-medium block mb-0.5">Phase 2 Georeference Raytrace Projection:</span>
          <span>Lat: {raytracedEstimate.latitude.toFixed(6)} | Lon: {raytracedEstimate.longitude.toFixed(6)}</span>
        </div>
      </div>

      <div className="p-3 rounded-lg bg-marine-950/40 border border-marine-800/60 text-slate-400 text-[11px] font-mono flex items-center justify-between">
        <span>Image Bounding Box [x, y, w, h]:</span>
        <span className="text-slate-200">[{detection.bbox.join(', ')}]</span>
      </div>
    </div>
  );
};
