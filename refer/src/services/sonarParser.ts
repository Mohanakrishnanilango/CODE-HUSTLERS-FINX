import { SonarSurvey, SonarPingRecord, ParseResult, SonarSide } from '../types/sonar';

export interface ISonarParser {
  supports(filename: string, headerBytes: Uint8Array, textSnippet: string): boolean;
  parse(file: File, textContent: string, buffer: ArrayBuffer): Promise<ParseResult>;
}

/**
 * Checks whether an uploaded file is genuine vendor binary XTF/JSF or a text test fixture.
 */
export function isBinarySonarFile(bytes: Uint8Array): boolean {
  // Check for non-printable binary characters / null bytes in first 64 bytes
  let nullBytesCount = 0;
  const sampleLength = Math.min(bytes.length, 128);
  for (let i = 0; i < sampleLength; i++) {
    if (bytes[i] === 0x00) {
      nullBytesCount++;
    }
  }
  // If > 2% null bytes in header, it's a binary file
  return nullBytesCount > 2;
}

/**
 * Modular parser for synthetic XTF/JSF text fixtures.
 */
export class SyntheticSonarParser implements ISonarParser {
  supports(filename: string, headerBytes: Uint8Array, textSnippet: string): boolean {
    const isBinary = isBinarySonarFile(headerBytes);
    if (isBinary) return false;
    const lower = filename.toLowerCase();
    const isSupportedExt = lower.endsWith('.xtf') || lower.endsWith('.jsf') || lower.endsWith('.txt') || lower.endsWith('.json');
    const isSyntheticText = textSnippet.includes('SYNTHETIC') || textSnippet.includes('[SURVEY_HEADER]') || textSnippet.includes('[PING_RECORD]');
    return isSupportedExt && isSyntheticText;
  }

  async parse(file: File, textContent: string, _buffer: ArrayBuffer): Promise<ParseResult> {
    const ext = file.name.toLowerCase().endsWith('.jsf') ? 'JSF' : 'XTF';
    const lines = textContent.split(/\r?\n/);

    const survey: SonarSurvey = {
      header: {
        survey_id: `SURVEY_${Date.now()}`,
        sonar_model: 'Synthetic Sonar Fixture',
        frequency_khz: 450,
        sample_rate_hz: 24000,
        total_pings: 0,
        georeference_status: 'NAV_METADATA_DIRECT'
      },
      pings: [],
      isSyntheticFixture: true,
      sourceFilename: file.name,
      fileFormat: ext
    };

    let currentSection = '';
    let currentPing: Partial<SonarPingRecord> | null = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.startsWith('#')) {
        continue;
      }

      if (line.startsWith('[') && line.endsWith(']')) {
        currentSection = line.slice(1, -1).toUpperCase();
        if (currentSection === 'PING_RECORD') {
          if (currentPing && this.validatePing(currentPing)) {
            survey.pings.push(this.completePing(currentPing));
          }
          currentPing = {};
        }
        continue;
      }

      const eqIndex = line.indexOf('=');
      if (eqIndex === -1) continue;

      const key = line.slice(0, eqIndex).trim().toLowerCase();
      const val = line.slice(eqIndex + 1).trim();

      if (currentSection === 'SURVEY_HEADER') {
        if (key === 'survey_id') survey.header.survey_id = val;
        else if (key === 'sonar_model') survey.header.sonar_model = val;
        else if (key === 'frequency_khz') survey.header.frequency_khz = parseFloat(val) || 450;
        else if (key === 'sample_rate_hz') survey.header.sample_rate_hz = parseFloat(val) || 24000;
        else if (key === 'total_pings') survey.header.total_pings = parseInt(val, 10) || 0;
        else if (key === 'georeference_status') survey.header.georeference_status = val;
      } else if (currentSection === 'PING_RECORD' && currentPing) {
        if (key === 'ping_id') currentPing.ping_id = parseInt(val, 10);
        else if (key === 'image') currentPing.image = val.startsWith('/') ? val : `/${val}`;
        else if (key === 'timestamp') currentPing.timestamp = val;
        else if (key === 'latitude') currentPing.latitude = parseFloat(val);
        else if (key === 'longitude') currentPing.longitude = parseFloat(val);
        else if (key === 'heading') currentPing.heading = parseFloat(val);
        else if (key === 'altitude') currentPing.altitude = parseFloat(val);
        else if (key === 'sonar_range') currentPing.sonar_range = parseFloat(val);
        else if (key === 'side') currentPing.side = val.toLowerCase() === 'port' ? 'port' : 'starboard';
        else if (key === 'target_class') currentPing.target_class = val.toLowerCase();
        else if (key === 'confidence') currentPing.confidence = parseFloat(val);
        else if (key === 'bbox') {
          const parts = val.split(',').map(n => parseFloat(n.trim()));
          if (parts.length === 4) {
            currentPing.bbox = [parts[0], parts[1], parts[2], parts[3]];
          }
        }
      }
    }

    if (currentPing && this.validatePing(currentPing)) {
      survey.pings.push(this.completePing(currentPing));
    }

    // Validation checks
    if (survey.pings.length === 0) {
      return {
        success: false,
        error: 'Corrupted file or empty detection result. No valid ping records could be extracted from synthetic fixture.'
      };
    }

    survey.header.total_pings = survey.pings.length;

    return {
      success: true,
      survey
    };
  }

  private validatePing(p: Partial<SonarPingRecord>): boolean {
    if (p.latitude === undefined || isNaN(p.latitude) || p.latitude < -90 || p.latitude > 90) {
      return false;
    }
    if (p.longitude === undefined || isNaN(p.longitude) || p.longitude < -180 || p.longitude > 180) {
      return false;
    }
    return true;
  }

  private completePing(p: Partial<SonarPingRecord>): SonarPingRecord {
    return {
      ping_id: p.ping_id ?? 1,
      image: p.image ?? '/images/ping_0001.png',
      timestamp: p.timestamp ?? new Date().toISOString(),
      latitude: p.latitude ?? 0,
      longitude: p.longitude ?? 0,
      heading: p.heading ?? 0,
      altitude: p.altitude ?? 15,
      sonar_range: p.sonar_range ?? 50,
      side: (p.side ?? 'starboard') as SonarSide,
      target_class: p.target_class ?? 'ghost_net',
      confidence: p.confidence ?? 0.85,
      bbox: p.bbox ?? [100, 100, 200, 200]
    };
  }
}

/**
 * Modular parser stub for genuine vendor binary XTF/JSF.
 * Designed to be replaced by WebAssembly / Python binary unpacker in Phase 2.
 */
export class RealVendorBinarySonarParser implements ISonarParser {
  supports(_filename: string, headerBytes: Uint8Array, _textSnippet: string): boolean {
    return isBinarySonarFile(headerBytes);
  }

  async parse(file: File, _textContent: string, _buffer: ArrayBuffer): Promise<ParseResult> {
    const isJsf = file.name.toLowerCase().endsWith('.jsf');
    const formatName = isJsf ? 'EdgeTech JSF Binary' : 'eXtended Triton Format (XTF) Binary';

    return {
      success: false,
      isRealBinary: true,
      error: `Real vendor ${formatName} detected (${(file.size / (1024 * 1024)).toFixed(2)} MB). Genuine vendor binary decoding module is reserved for Phase 2 integration. Please use the synthetic development test fixture (.xtf / .jsf) or click "Load Sample Survey Fixture".`
    };
  }
}

/**
 * Main parser entrypoint with file inspection and routing.
 */
export async function parseSonarLogFile(file: File): Promise<ParseResult> {
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (ext !== 'xtf' && ext !== 'jsf') {
    return {
      success: false,
      error: `Unsupported file format (.${ext || 'unknown'}). Please provide an .XTF or .JSF sonar survey log file.`
    };
  }

  try {
    const buffer = await file.arrayBuffer();
    const headerBytes = new Uint8Array(buffer.slice(0, 512));
    const textSnippet = new TextDecoder('utf-8', { fatal: false }).decode(headerBytes);

    const binaryParser = new RealVendorBinarySonarParser();
    if (binaryParser.supports(file.name, headerBytes, textSnippet)) {
      return await binaryParser.parse(file, textSnippet, buffer);
    }

    const fullText = await file.text();
    const syntheticParser = new SyntheticSonarParser();
    return await syntheticParser.parse(file, fullText, buffer);
  } catch (err: any) {
    return {
      success: false,
      error: `Corrupted file or read error: ${err.message || String(err)}`
    };
  }
}
