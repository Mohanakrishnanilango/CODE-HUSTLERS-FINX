import { SonarSide } from './sonar';

export type TargetClass = 
  | 'fishing_gear'
  | 'ghost_net'
  | 'pipeline'
  | 'shipwreck'
  | 'mine_cylinder';

export interface DetectionResult {
  id: string;
  ping_id: number;
  object_class: TargetClass | string;
  display_name: string;
  confidence: number;
  latitude: number;
  longitude: number;
  timestamp: string;
  heading_deg: number;
  altitude_m: number;
  range_m: number;
  side: SonarSide;
  bbox: [number, number, number, number]; // [x, y, width, height]
  image_url: string;
  is_synthetic: boolean;
  position_label: string; // e.g. "Detection position from navigation metadata"
}

export interface SurveySummaryData {
  totalRecords: number;
  totalDetections: number;
  classCounts: Record<string, number>;
  averageConfidence: number;
}
