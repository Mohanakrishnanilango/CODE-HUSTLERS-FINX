import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import { SonarUploader } from '../components/SonarUploader';
import { SonarViewer } from '../components/SonarViewer';
import { SonarMap } from '../components/SonarMap';
import { DetectionTable } from '../components/DetectionTable';
import { DetectionDetails } from '../components/DetectionDetails';
import { SurveySummary } from '../components/SurveySummary';
import { ReportButtons } from '../components/ReportButtons';
import { SonarSurvey } from '../types/sonar';
import { DetectionResult } from '../types/detection';
import { DEFAULT_SYNTHETIC_SURVEY } from '../data/synthetic/fixtures';
import { activeDetector } from '../services/detectionService';

export const Dashboard: React.FC = () => {
  const [activeSection, setActiveSection] = useState<string>('upload');
  const [survey, setSurvey] = useState<SonarSurvey | null>(DEFAULT_SYNTHETIC_SURVEY);
  const [detections, setDetections] = useState<DetectionResult[]>([]);
  const [selectedDetectionId, setSelectedDetectionId] = useState<string | null>(null);
  const [selectedPingId, setSelectedPingId] = useState<number>(1);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  // Process pings through detector whenever survey changes
  useEffect(() => {
    if (!survey || survey.pings.length === 0) {
      setDetections([]);
      setSelectedDetectionId(null);
      return;
    }

    setIsProcessing(true);
    activeDetector.detect(survey.pings)
      .then((results) => {
        setDetections(results);
        if (results.length > 0) {
          setSelectedDetectionId(results[0].id);
          setSelectedPingId(results[0].ping_id);
        }
      })
      .finally(() => {
        setIsProcessing(false);
      });
  }, [survey]);

  // Synchronized selection handler
  const handleSelectDetection = (detectionId: string, pingId: number) => {
    setSelectedDetectionId(detectionId);
    setSelectedPingId(pingId);
  };

  // Synchronized ping selector handler
  const handleSelectPing = (pingId: number) => {
    setSelectedPingId(pingId);
    const matchingDet = detections.find(d => d.ping_id === pingId);
    if (matchingDet) {
      setSelectedDetectionId(matchingDet.id);
    }
  };

  const handleSelectSection = (section: string) => {
    setActiveSection(section);
    const element = document.getElementById(`section-${section}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const selectedDetection = detections.find(d => d.id === selectedDetectionId) || detections[0] || null;

  return (
    <div className="min-h-screen bg-marine-950 flex flex-col font-sans">
      <Header />

      <div className="flex-1 flex flex-col md:flex-row">
        {/* Navigation Sidebar */}
        <Sidebar activeSection={activeSection} onSelectSection={handleSelectSection} />

        {/* Main Content Dashboard */}
        <main className="flex-1 p-4 md:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto w-full">
          {/* Section 1: Upload */}
          <div id="section-upload">
            <SonarUploader
              currentSurvey={survey}
              onSurveyLoaded={(newSurvey) => setSurvey(newSurvey)}
              isProcessing={isProcessing}
            />
          </div>

          {/* Section 2: Survey Overview */}
          <div id="section-overview">
            <SurveySummary
              totalRecords={survey?.pings.length || 0}
              detections={detections}
            />
          </div>

          {/* Section 3: Imagery & Telemetry Split View */}
          <div id="section-detections" className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <SonarViewer
                pings={survey?.pings || []}
                selectedPingId={selectedPingId}
                onSelectPing={handleSelectPing}
                detection={selectedDetection}
              />
            </div>
            <div>
              <DetectionDetails detection={selectedDetection} />
            </div>
          </div>

          {/* Section 4: Map */}
          <div id="section-map">
            <SonarMap
              detections={detections}
              selectedDetectionId={selectedDetectionId}
              onSelectDetection={handleSelectDetection}
            />
          </div>

          {/* Detections Register Table */}
          <div>
            <DetectionTable
              detections={detections}
              selectedDetectionId={selectedDetectionId}
              onSelectDetection={handleSelectDetection}
            />
          </div>

          {/* Section 5: Reports */}
          <div id="section-reports">
            <ReportButtons
              surveyId={survey?.header.survey_id || 'SURVEY_UNKNOWN'}
              sourceFilename={survey?.sourceFilename || 'survey.xtf'}
              detections={detections}
            />
          </div>
        </main>
      </div>
    </div>
  );
};
