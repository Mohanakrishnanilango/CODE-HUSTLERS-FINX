import React, { useRef, useState } from 'react';
import { UploadCloud, CheckCircle2, AlertCircle, FileCode, Play, Download, Loader2 } from 'lucide-react';
import { parseSonarLogFile } from '../services/sonarParser';
import { SonarSurvey } from '../types/sonar';
import { DEFAULT_SYNTHETIC_SURVEY } from '../data/synthetic/fixtures';

interface SonarUploaderProps {
  currentSurvey: SonarSurvey | null;
  onSurveyLoaded: (survey: SonarSurvey) => void;
  isProcessing: boolean;
}

export const SonarUploader: React.FC<SonarUploaderProps> = ({
  currentSurvey,
  onSurveyLoaded,
  isProcessing
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await processFile(file);
  };

  const processFile = async (file: File) => {
    setErrorMessage(null);
    setWarningMessage(null);

    try {
      const result = await parseSonarLogFile(file);

      if (!result.success) {
        if (result.isRealBinary) {
          setWarningMessage(result.error || 'Binary file detected');
        } else {
          setErrorMessage(result.error || 'Failed to parse file');
        }
        return;
      }

      if (result.survey) {
        onSurveyLoaded(result.survey);
      }
    } catch (err: any) {
      setErrorMessage(`Error reading sonar log: ${err.message || String(err)}`);
    }
  };

  const loadDefaultFixture = () => {
    setErrorMessage(null);
    setWarningMessage(null);
    onSurveyLoaded(DEFAULT_SYNTHETIC_SURVEY);
  };

  return (
    <div className="bg-marine-900 border border-marine-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-marine-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-sonar-cyan" />
            Upload XTF / JSF Sonar Log
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Supported side-scan sonar log formats: <span className="font-mono text-slate-200">.XTF</span>, <span className="font-mono text-slate-200">.JSF</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={loadDefaultFixture}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sonar-cyan/15 text-sonar-cyan hover:bg-sonar-cyan/25 border border-sonar-cyan/30 text-xs font-medium transition-colors"
            title="Load the 5 synthetic testbed pings with high-precision annotations"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            Load Sample Survey Fixture
          </button>

          <a
            href="/fixtures/sonar_survey_001.xtf"
            download="sonar_survey_001.xtf"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-marine-800 text-slate-300 hover:text-white hover:bg-marine-700 border border-marine-700 text-xs font-medium transition-colors"
            title="Download synthetic XTF file to test file drop"
          >
            <Download className="w-3.5 h-3.5" />
            Download .XTF Fixture
          </a>
        </div>
      </div>

      {/* Upload Drag & Drop Box */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files?.[0];
          if (file) processFile(file);
        }}
        className="border-2 border-dashed border-marine-700 hover:border-sonar-cyan/60 rounded-xl p-6 text-center cursor-pointer transition-all bg-marine-950/40 hover:bg-marine-950/80 group"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".xtf,.jsf,.txt"
          onChange={handleFileChange}
          className="hidden"
        />
        <div className="flex flex-col items-center space-y-2">
          <div className="w-12 h-12 rounded-full bg-marine-800 flex items-center justify-center group-hover:scale-110 transition-transform">
            <FileCode className="w-6 h-6 text-sonar-cyan" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-200">
              Click or drag & drop sonar log here
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              Select <span className="font-mono text-sonar-cyan">sonar_survey_001.xtf</span> or <span className="font-mono text-sonar-cyan">sonar_survey_001.jsf</span>
            </p>
          </div>
        </div>
      </div>

      {/* Warning Alert (for real binary file) */}
      {warningMessage && (
        <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block text-amber-300">Binary Sonar Log Notice</span>
            {warningMessage}
          </div>
        </div>
      )}

      {/* Error Alert */}
      {errorMessage && (
        <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-200 text-xs flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block text-rose-300">Parser Error</span>
            {errorMessage}
          </div>
        </div>
      )}

      {/* Processing Status Checklist */}
      {currentSurvey && (
        <div className="bg-marine-950/80 border border-marine-800 rounded-lg p-4 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-marine-800 text-slate-300">
            <span className="font-semibold text-sonar-cyan">{currentSurvey.sourceFilename}</span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-marine-800 text-slate-300 border border-marine-700">
              {currentSurvey.fileFormat} Format
            </span>
          </div>

          <div className="mt-3 space-y-1.5">
            <div className="text-slate-400 font-semibold mb-1">Status:</div>
            
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 className="w-4 h-4 text-sonar-green shrink-0" />
              <span>Log loaded ({currentSurvey.header.sonar_model})</span>
            </div>

            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 className="w-4 h-4 text-sonar-green shrink-0" />
              <span>{currentSurvey.pings.length} sonar records extracted</span>
            </div>

            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 className="w-4 h-4 text-sonar-green shrink-0" />
              <span>Navigation metadata available ({currentSurvey.header.georeference_status})</span>
            </div>

            <div className="flex items-center gap-2 text-emerald-400">
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 text-sonar-cyan animate-spin shrink-0" />
                  <span className="text-sonar-cyan">Running detector inference...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 text-sonar-green shrink-0" />
                  <span>Detection complete (Synthetic Sonar Detector)</span>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
