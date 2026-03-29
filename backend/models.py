from pydantic import BaseModel
from typing import Optional, List



class GPSReading(BaseModel):
    timestamp   : str
    latitude    : float
    longitude   : float
    altitude_m  : float
    speed_kmph  : float
    satellites  : int



class AccidentReport(BaseModel):

    # ── Core fields
    session_id          : str
    report_text         : str
    generated_at        : str

    # ── Location
    crash_gps           : Optional[str]  = None
    nearest_landmark    : Optional[str]  = None
    google_maps_link    : Optional[str]  = None

    # ── Environmental
    weather_at_crash    : Optional[str]  = None
    weather_risk        : Optional[str]  = None
    speed_limit         : Optional[str]  = None
    road_type           : Optional[str]  = None

    # ── Crash analysis
    severity            : Optional[str]  = None
    max_speed_kmph      : Optional[float]= None
    pre_crash_speed     : Optional[float]= None
    speed_drop_kmph     : Optional[float]= None
    deceleration_g      : Optional[float]= None
    speed_trend         : Optional[str]  = None
    crash_timestamp     : Optional[str]  = None
    satellites_lost     : Optional[bool] = None

    # ── Confidence fields (NEW)
    confidence          : Optional[str]  = None   # HIGH / MEDIUM / LOW / NONE
    confidence_pct      : Optional[int]  = None   # 0-100
    confirmed_facts     : Optional[List[str]] = None  # what data is confirmed
    unavailable_data    : Optional[List[str]] = None  # what could not be determined
    low_confidence_data : Optional[List[str]] = None  # what is uncertain

    # ── Legal & safety (NEW)
    legal_note          : Optional[str]  = None
    limitations         : Optional[List[str]] = None
    injury_risk         : Optional[str]  = None
    emergency_action    : Optional[str]  = None

    # ── Data sources (NEW)
    data_sources        : Optional[List[str]] = None