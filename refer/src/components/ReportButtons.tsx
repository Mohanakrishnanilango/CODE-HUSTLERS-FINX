import React from 'react';
import { DetectionResult } from '../types/detection';
import { ReportService } from '../services/reportService';
import { FileJson, FileSpreadsheet, Download } from 'lucide-react';

interface ReportButtonsProps {
  surveyId: string;
  sourceFilename: string;
  detections: DetectionResult[];
}

export const ReportButtons: React.FC<ReportButtonsProps> = ({
  surveyId,
  sourceFilename,
  detections
}) => {
  const handleDownloadJson = () => {
    const jsonContent = ReportService.generateJsonReport(surveyId, sourceFilename, detections);
    ReportService.triggerDownload(
      jsonContent,
      `${surveyId}_detections.json`,
      'application/json'
    );
  };

  const handleDownloadCsv = () => {
    const csvContent = ReportService.generateCsvReport(surveyId, detections);
    ReportService.triggerDownload(
      csvContent,
      `${surveyId}_detections.csv`,
      'text/csv;charset=utf-8;'
    );
  };

  return (
    <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-marine-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Download className="w-5 h-5 text-sonar-cyan" />
            Georeferenced Reports & Data Export
          </h2>
          <p className="text-xs text-slate-400">
            Export georeferenced anomaly detections with spatial and navigation telemetry
          </p>
        </div>

        <span className="text-xs font-mono text-slate-400">
          Ready for GIS & Hydrographic processing
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleDownloadJson}
          disabled={detections.length === 0}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-sonar-cyan/15 text-sonar-cyan hover:bg-sonar-cyan/25 border border-sonar-cyan/40 text-sm font-medium transition-all shadow-sm hover:shadow-sonar-cyan disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <FileJson className="w-4 h-4" />
          <span>Download JSON Report</span>
        </button>

        <button
          onClick={handleDownloadCsv}
          disabled={detections.length === 0}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-marine-800 text-slate-200 hover:text-white hover:bg-marine-700 border border-marine-700 text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <FileSpreadsheet className="w-4 h-4 text-sonar-green" />
          <span>Download CSV Report</span>
        </button>
      </div>
    </div>
  );
};
