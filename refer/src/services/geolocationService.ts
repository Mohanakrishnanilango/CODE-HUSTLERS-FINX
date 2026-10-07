import { SonarSide } from '../types/sonar';

export interface GeolocationInput {
  gps_latitude: number;
  gps_longitude: number;
  heading_deg: number;
  altitude_m: number;
  sonar_range_m: number;
  side: SonarSide;
  bbox_pixel_x?: number;
  image_width_px?: number;
}

export interface GeolocationResult {
  latitude: number;
  longitude: number;
  method: 'direct_navigation' | 'slant_range_raytrace';
  label: string;
}

/**
 * Geolocation Service.
 * In current MVP: Directly maps vessel/towfish navigation coordinates.
 * Structured with extensible raytrace calculation interface for Phase 2.
 */
export class GeolocationService {
  /**
   * MVP: Returns navigation latitude and longitude directly.
   * Notice: Explicitly labelled as "Detection position from navigation metadata".
   */
  static getDetectionCoordinates(input: GeolocationInput): GeolocationResult {
    return {
      latitude: input.gps_latitude,
      longitude: input.gps_longitude,
      method: 'direct_navigation',
      label: 'Detection position from navigation metadata'
    };
  }

  /**
   * Future Phase 2 Architecture:
   * Estimates true seabed debris position using:
   * GPS + towfish heading + slant range + across-track offset + altitude (bathymetry)
   */
  static computeTrueSeabedTargetLocation(input: GeolocationInput): GeolocationResult {
    // Phase 2 geometric seabed offset projection:
    // Across-track horizontal distance: dh = sqrt(R^2 - h^2)
    // Lateral bearing: heading +/- 90 degrees depending on port/starboard
    // Earth radius: R_earth = 6378137 m
    const { gps_latitude, gps_longitude, heading_deg, altitude_m, sonar_range_m, side } = input;
    
    // Slant range to horizontal ground range
    const groundRange = Math.sqrt(Math.max(0, (sonar_range_m * sonar_range_m) - (altitude_m * altitude_m)));
    
    // Bearing angle perpendicular to vessel track
    const bearingOffset = side === 'port' ? -90 : 90;
    const targetBearing = (heading_deg + bearingOffset + 360) % 360;
    const bearingRad = (targetBearing * Math.PI) / 180;
    
    // Earth coordinate delta (WGS-84 spherical approx)
    const R_earth = 6378137;
    const dLat = (groundRange * Math.cos(bearingRad)) / R_earth;
    const dLon = (groundRange * Math.sin(bearingRad)) / (R_earth * Math.cos((gps_latitude * Math.PI) / 180));
    
    const targetLat = gps_latitude + (dLat * 180) / Math.PI;
    const targetLon = gps_longitude + (dLon * 180) / Math.PI;

    return {
      latitude: targetLat,
      longitude: targetLon,
      method: 'slant_range_raytrace',
      label: 'Estimated seabed georeferenced position (Towfish acoustic raytrace)'
    };
  }
}
