import { SonarPingRecord } from '../types/sonar';
import { DetectionResult, TargetClass } from '../types/detection';

export interface IDetector {
  name: string;
  isRealModel: boolean;
  detect(pings: SonarPingRecord[]): Promise<DetectionResult[]>;
  detectSingle(ping: SonarPingRecord): Promise<DetectionResult | null>;
}

export const CLASS_FORMATTERS: Record<string, { label: string; color: string; badgeClass: string; markerColor: string }> = {
  ghost_net: {
    label: 'Ghost Net',
    color: '#FFB800', // Amber
    badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    markerColor: '#FFB800'
  },
  pipeline: {
    label: 'Pipeline',
    color: '#00F0FF', // Cyan
    badgeClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    markerColor: '#00F0FF'
  },
  shipwreck: {
    label: 'Shipwreck',
    color: '#FF3366', // Crimson
    badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    markerColor: '#FF3366'
  },
  fishing_gear: {
    label: 'Fishing Gear',
    color: '#00FF66', // Phosphor Green
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    markerColor: '#00FF66'
  },
  mine_cylinder: {
    label: 'Mine Cylinder',
    color: '#B026FF', // Purple
    badgeClass: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    markerColor: '#B026FF'
  }
};

export function formatTargetClass(cls: string): string {
  const norm = cls.toLowerCase();
  return CLASS_FORMATTERS[norm]?.label || cls.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Synthetic Detector implementation for current testbed fixture.
 */
export class SyntheticDetector implements IDetector {
  name = 'Synthetic Sonar Detector (MVP Testbed)';
  isRealModel = false;

  async detect(pings: SonarPingRecord[]): Promise<DetectionResult[]> {
    const results: DetectionResult[] = [];
    for (const ping of pings) {
      const det = await this.detectSingle(ping);
      if (det) results.push(det);
    }
    return results;
  }

  async detectSingle(ping: SonarPingRecord): Promise<DetectionResult | null> {
    if (!ping.target_class || ping.confidence === 0) {
      return null;
    }

    return {
      id: `det_ping_${ping.ping_id}`,
      ping_id: ping.ping_id,
      object_class: ping.target_class as TargetClass,
      display_name: formatTargetClass(ping.target_class),
      confidence: ping.confidence,
      latitude: ping.latitude,
      longitude: ping.longitude,
      timestamp: ping.timestamp,
      heading_deg: ping.heading,
      altitude_m: ping.altitude,
      range_m: ping.sonar_range,
      side: ping.side,
      bbox: ping.bbox,
      image_url: ping.image,
      is_synthetic: true,
      position_label: 'Detection position from navigation metadata'
    };
  }
}

/**
 * Future Faster R-CNN (ResNet-50 FPN) detector interface.
 * Connects to the local FastAPI PyTorch inference microservice.
 */
export class FasterRCNNDetector implements IDetector {
  name = 'High-Precision Acoustic Detector';
  isRealModel = true;
  private apiEndpoint: string;

  constructor(apiEndpoint = 'http://localhost:8000/api/detect') {
    this.apiEndpoint = apiEndpoint;
  }

  async detect(pings: SonarPingRecord[]): Promise<DetectionResult[]> {
    try {
      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pings })
      });
      if (!response.ok) {
        throw new Error(`Inference server responded with ${response.status}`);
      }
      const data = await response.json();
      return data.detections;
    } catch (err) {
      console.warn('Faster R-CNN inference service unavailable, fallback required.', err);
      throw err;
    }
  }

  async detectSingle(ping: SonarPingRecord): Promise<DetectionResult | null> {
    const results = await this.detect([ping]);
    return results.length > 0 ? results[0] : null;
  }
}

// Active detector singleton (defaults to SyntheticDetector for MVP)
export let activeDetector: IDetector = new SyntheticDetector();

export function setDetector(detector: IDetector) {
  activeDetector = detector;
}
