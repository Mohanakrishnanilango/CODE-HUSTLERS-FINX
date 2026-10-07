from typing import Optional
from pydantic import BaseModel, Field


class SurveyMetadata(BaseModel):
    """
    Survey and side-scan sonar acquisition metadata.
    Never fabricated if missing.
    """
    survey_latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Survey vessel or towfish latitude in WGS84 decimal degrees"
    )
    survey_longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Survey vessel or towfish longitude in WGS84 decimal degrees"
    )
    heading_deg: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=360.0,
        description="Vessel/towfish heading in degrees clockwise from true North"
    )
    resolution_m_per_pixel: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Spatial resolution of the SSS image in meters per pixel"
    )
    nadir_column: Optional[int] = Field(
        default=None,
        ge=0,
        description="Pixel column corresponding to the sonar nadir/track line"
    )
    swath_channel: Optional[str] = Field(
        default=None,
        description="Acoustic channel: 'port', 'starboard', or 'both'"
    )
    altitude_m: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Towfish altitude above seabed in meters"
    )
    slant_range_m: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Maximum slant range of the sonar ping in meters"
    )
    sonar_frequency_khz: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Operating frequency of the sonar in kHz"
    )
    acquisition_timestamp: Optional[str] = Field(
        default=None,
        description="ISO 8601 acquisition timestamp"
    )
