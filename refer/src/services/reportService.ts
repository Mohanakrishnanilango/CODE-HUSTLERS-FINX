import { DetectionResult } from '../types/detection';

export interface SurveyReportExportData {
  survey_id: string;
  source_file: string;
  generated_at: string;
  total_detections: number;
  detections: Array<{
    ping_id: number;
    object_class: string;
    confidence: number;
    latitude: number;
    longitude: number;
    timestamp: string;
    heading_deg: number;
    altitude_m: number;
    range_m: number;
    side: string;
    bbox: [number, number, number, number];
  }>;
}

export class ReportService {
  /**
   * Generates formatted JSON data matching requirement specification.
   */
  static generateJsonReport(surveyId: string, sourceFilename: string, detections: DetectionResult[]): string {
    const report: SurveyReportExportData = {
      survey_id: surveyId,
      source_file: sourceFilename,
      generated_at: new Date().toISOString(),
      total_detections: detections.length,
      detections: detections.map(d => ({
        ping_id: d.ping_id,
        object_class: d.object_class,
        confidence: d.confidence,
        latitude: d.latitude,
        longitude: d.longitude,
        timestamp: d.timestamp,
        heading_deg: d.heading_deg,
        altitude_m: d.altitude_m,
        range_m: d.range_m,
        side: d.side,
        bbox: d.bbox
      }))
    };

    return JSON.stringify(report, null, 2);
  }

  /**
   * Generates CSV format with equivalent columns.
   */
  static generateCsvReport(surveyId: string, detections: DetectionResult[]): string {
    const headers = [
      'survey_id',
      'ping_id',
      'object_class',
      'confidence',
      'latitude',
      'longitude',
      'timestamp',
      'heading_deg',
      'altitude_m',
      'range_m',
      'side',
      'bbox_x',
      'bbox_y',
      'bbox_width',
      'bbox_height',
      'position_source'
    ];

    const rows = detections.map(d => [
      `"${surveyId}"`,
      d.ping_id,
      `"${d.object_class}"`,
      d.confidence.toFixed(4),
      d.latitude.toFixed(6),
      d.longitude.toFixed(6),
      `"${d.timestamp}"`,
      d.heading_deg.toFixed(1),
      d.altitude_m.toFixed(1),
      d.range_m.toFixed(1),
      `"${d.side}"`,
      d.bbox[0],
      d.bbox[1],
      d.bbox[2],
      d.bbox[3],
      `"${d.position_label}"`
    ]);

    return [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n');
  }

  /**
   * Helper to trigger browser file download.
   */
  static triggerDownload(content: string, filename: string, mimeType: string) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}
