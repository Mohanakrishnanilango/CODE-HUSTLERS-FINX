import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { DetectionResult } from '../types/detection';
import { CLASS_FORMATTERS } from '../services/detectionService';
import { MapPin, Navigation2, Layers } from 'lucide-react';

interface SonarMapProps {
  detections: DetectionResult[];
  selectedDetectionId: string | null;
  onSelectDetection: (detectionId: string, pingId: number) => void;
}

/**
 * Controller to fit bounds and smoothly fly/pan to selected marker.
 */
function MapBoundsController({
  detections,
  selectedDetection
}: {
  detections: DetectionResult[];
  selectedDetection: DetectionResult | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (detections.length === 0) return;

    if (selectedDetection) {
      map.panTo([selectedDetection.latitude, selectedDetection.longitude], {
        animate: true,
        duration: 0.6
      });
    } else {
      const bounds = L.latLngBounds(detections.map(d => [d.latitude, d.longitude]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 17 });
    }
  }, [detections, selectedDetection, map]);

  return null;
}

/**
 * Helper to build custom colored SVG DivIcons for Leaflet.
 */
function createCustomMarkerIcon(targetClass: string, isSelected: boolean) {
  const formatter = CLASS_FORMATTERS[targetClass.toLowerCase()] || {
    color: '#00F0FF',
    label: targetClass
  };

  const color = formatter.color;
  const pulseClass = isSelected ? 'animate-ping' : '';
  const size = isSelected ? 34 : 28;

  const html = `
    <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center;">
      ${isSelected ? `<div style="position: absolute; width: ${size + 14}px; height: ${size + 14}px; border-radius: 50%; border: 2px solid ${color}; opacity: 0.6;" class="${pulseClass}"></div>` : ''}
      <div style="
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        background-color: #0B132B;
        border: 2px solid ${color};
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 0 ${isSelected ? '14px' : '8px'} ${color};
        cursor: pointer;
      ">
        <svg width="${size * 0.55}" height="${size * 0.55}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <circle cx="12" cy="12" r="3" fill="${color}"></circle>
          <line x1="12" y1="2" x2="12" y2="6"></line>
          <line x1="12" y1="18" x2="12" y2="22"></line>
          <line x1="2" y1="12" x2="6" y2="12"></line>
          <line x1="18" y1="12" x2="22" y2="12"></line>
        </svg>
      </div>
    </div>
  `;

  return L.divIcon({
    className: 'custom-sonar-marker',
    html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2]
  });
}

export const SonarMap: React.FC<SonarMapProps> = ({
  detections,
  selectedDetectionId,
  onSelectDetection
}) => {
  const selectedDetection = useMemo(
    () => detections.find(d => d.id === selectedDetectionId) || null,
    [detections, selectedDetectionId]
  );

  // Compute center
  const centerPosition: [number, number] = useMemo(() => {
    if (detections.length === 0) return [9.9520, 76.1250];
    const avgLat = detections.reduce((sum, d) => sum + d.latitude, 0) / detections.length;
    const avgLon = detections.reduce((sum, d) => sum + d.longitude, 0) / detections.length;
    return [avgLat, avgLon];
  }, [detections]);

  // Towfish survey track line
  const trackPath: [number, number][] = useMemo(() => {
    return detections.map(d => [d.latitude, d.longitude]);
  }, [detections]);

  return (
    <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-marine-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <MapPin className="w-5 h-5 text-sonar-cyan" />
            Georeferenced Detection Map
          </h2>
          <p className="text-xs text-slate-400">
            OpenStreetMap Tiles | Georeference: <span className="font-mono text-sonar-cyan">Direct Towfish Navigation</span>
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 font-mono text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full bg-sonar-cyan"></span>
            <span>{detections.length} Target Markers</span>
          </div>
          <div className="text-[11px] px-2 py-0.5 rounded bg-marine-800 text-slate-400 border border-marine-700">
            No Geocoding API (Direct GPS)
          </div>
        </div>
      </div>

      {/* Map Legend */}
      <div className="flex flex-wrap items-center gap-3 p-2.5 rounded-lg bg-marine-950/80 border border-marine-800 text-xs font-mono">
        <span className="text-slate-400 font-semibold flex items-center gap-1">
          <Layers className="w-3.5 h-3.5" /> Classes:
        </span>
        {Object.entries(CLASS_FORMATTERS).map(([key, val]) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: val.color }} />
            <span className="text-slate-300 text-[11px]">{val.label}</span>
          </div>
        ))}
      </div>

      {/* Leaflet Map Canvas */}
      <div className="h-[420px] w-full rounded-lg overflow-hidden border border-marine-700 relative">
        <MapContainer
          center={centerPosition}
          zoom={16}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%' }}
        >
          {/* OpenStreetMap standard tiles */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />

          <MapBoundsController detections={detections} selectedDetection={selectedDetection} />

          {/* Survey trackline */}
          {trackPath.length > 1 && (
            <Polyline
              positions={trackPath}
              pathOptions={{
                color: '#00F0FF',
                weight: 2,
                dashArray: '6, 6',
                opacity: 0.6
              }}
            />
          )}

          {/* Leaflet Markers for each detection */}
          {detections.map((det) => {
            const isSelected = det.id === selectedDetectionId;
            const icon = createCustomMarkerIcon(det.object_class, isSelected);

            return (
              <Marker
                key={det.id}
                position={[det.latitude, det.longitude]}
                icon={icon}
                eventHandlers={{
                  click: () => onSelectDetection(det.id, det.ping_id)
                }}
              >
                <Popup>
                  <div className="p-1 font-mono text-xs space-y-1.5 min-w-[210px]">
                    <div className="border-b border-marine-700 pb-1 flex items-center justify-between">
                      <span className="font-bold text-white text-sm">
                        {det.display_name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-medium">
                        Synthetic
                      </span>
                    </div>

                    <div className="space-y-0.5 text-slate-300">
                      <div>
                        <strong className="text-slate-400">Object: </strong>
                        <span className="text-white">{det.display_name}</span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Confidence: </strong>
                        <span className="text-sonar-green font-bold">
                          {Math.round(det.confidence * 100)}%
                        </span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Latitude: </strong>
                        <span className="text-slate-100">{det.latitude.toFixed(6)}</span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Longitude: </strong>
                        <span className="text-slate-100">{det.longitude.toFixed(6)}</span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Timestamp: </strong>
                        <span className="text-slate-300">{det.timestamp}</span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Heading: </strong>
                        <span className="text-slate-200">{det.heading_deg.toFixed(1)}°</span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Altitude: </strong>
                        <span className="text-slate-200">{det.altitude_m.toFixed(1)} m</span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Range: </strong>
                        <span className="text-slate-200">{det.range_m.toFixed(0)} m</span>
                      </div>
                      <div>
                        <strong className="text-slate-400">Side: </strong>
                        <span className="capitalize text-slate-200">{det.side}</span>
                      </div>
                    </div>

                    <div className="pt-1.5 mt-1 border-t border-marine-800 text-[10px] text-slate-400 italic">
                      {det.position_label}
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>

      <div className="text-[11px] font-mono text-slate-400 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <Navigation2 className="w-3.5 h-3.5 text-sonar-cyan" />
          Click any marker on the map to synchronize Sonar Imagery, Bounding Box, and Telemetry details.
        </span>
        <span className="text-slate-500">Coordinate Datum: WGS 84</span>
      </div>
    </div>
  );
};
