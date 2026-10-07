export type SonarSide = 'port' | 'starboard';

export interface BoundingBox {
  x: number;      // Pixel coordinate or percentage
  y: number;
  width: number;
  height: number;
}

export interface SonarPingRecord {
  ping_id: number;
  image: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  heading: number;     // degrees
  altitude: number;    // meters
  sonar_range: number; // meters
  side: SonarSide;
  target_class: string;
  confidence: number;  // 0.0 to 1.0
  bbox: [number, number, number, number]; // [x, y, width, height]
  raw_text?: string;
}

export interface SurveyHeader {
  survey_id: string;
  sonar_model: string;
  frequency_khz: number;
  sample_rate_hz: number;
  total_pings: number;
  georeference_status: string;
}

export interface SonarSurvey {
  header: SurveyHeader;
  pings: SonarPingRecord[];
  isSyntheticFixture: boolean;
  sourceFilename: string;
  fileFormat: 'XTF' | 'JSF' | 'UNKNOWN';
}

export interface ParseResult {
  success: boolean;
  survey?: SonarSurvey;
  isRealBinary?: boolean;
  error?: string;
  warning?: string;
}
