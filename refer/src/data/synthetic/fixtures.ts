import { SonarSurvey, SonarPingRecord } from '../../types/sonar';

export const SYNTHETIC_PING_RECORDS: SonarPingRecord[] = [
  {
    ping_id: 1,
    image: '/images/ping_0001.png',
    timestamp: '2026-09-23T09:30:01Z',
    latitude: 9.952000,
    longitude: 76.125000,
    heading: 82.8,
    altitude: 18.2,
    sonar_range: 50.0,
    side: 'starboard',
    target_class: 'ghost_net',
    confidence: 0.91,
    bbox: [140, 160, 260, 280] // [x, y, width, height]
  },
  {
    ping_id: 2,
    image: '/images/ping_0002.png',
    timestamp: '2026-09-23T09:30:02Z',
    latitude: 9.952500,
    longitude: 76.125700,
    heading: 83.1,
    altitude: 18.0,
    sonar_range: 50.0,
    side: 'port',
    target_class: 'pipeline',
    confidence: 0.87,
    bbox: [100, 240, 420, 120]
  },
  {
    ping_id: 3,
    image: '/images/ping_0003.png',
    timestamp: '2026-09-23T09:30:03Z',
    latitude: 9.951400,
    longitude: 76.124400,
    heading: 82.5,
    altitude: 18.4,
    sonar_range: 50.0,
    side: 'starboard',
    target_class: 'shipwreck',
    confidence: 0.84,
    bbox: [190, 180, 310, 240]
  },
  {
    ping_id: 4,
    image: '/images/ping_0004.png',
    timestamp: '2026-09-23T09:30:04Z',
    latitude: 9.952900,
    longitude: 76.126600,
    heading: 83.5,
    altitude: 17.9,
    sonar_range: 50.0,
    side: 'port',
    target_class: 'fishing_gear',
    confidence: 0.79,
    bbox: [210, 130, 190, 170]
  },
  {
    ping_id: 5,
    image: '/images/ping_0005.png',
    timestamp: '2026-09-23T09:30:05Z',
    latitude: 9.951000,
    longitude: 76.126100,
    heading: 82.0,
    altitude: 18.6,
    sonar_range: 50.0,
    side: 'starboard',
    target_class: 'mine_cylinder',
    confidence: 0.73,
    bbox: [280, 260, 110, 80]
  }
];

export const DEFAULT_SYNTHETIC_SURVEY: SonarSurvey = {
  header: {
    survey_id: 'SONAR_SURVEY_2026_001',
    sonar_model: 'EdgeTech_4200_Synthetic',
    frequency_khz: 410,
    sample_rate_hz: 25000,
    total_pings: 5,
    georeference_status: 'NAV_METADATA_DIRECT'
  },
  pings: SYNTHETIC_PING_RECORDS,
  isSyntheticFixture: true,
  sourceFilename: 'sonar_survey_001.xtf',
  fileFormat: 'XTF'
};
