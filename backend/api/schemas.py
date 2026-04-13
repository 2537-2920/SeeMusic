"""Request/response schemas for the API layer."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    start_time: float = Field(0, ge=0)
    end_time: float = Field(..., gt=0)


class PitchSequenceItem(BaseModel):
    time: float
    frequency: float
    duration: Optional[float] = None
    confidence: Optional[float] = None


class PitchCompareRequest(BaseModel):
    reference_id: str
    user_recording_id: str
    range: Optional[TimeRange] = None


class PitchToScoreRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    title: Optional[str] = None
    analysis_id: Optional[str] = None
    tempo: int = 120
    time_signature: str = "4/4"
    key_signature: str = "C"
    pitch_sequence: List[PitchSequenceItem]


class ScoreOperation(BaseModel):
    type: Literal[
        "add_note",
        "delete_note",
        "update_note",
        "update_time_signature",
        "update_key_signature",
        "update_tempo",
    ]
    measure_no: Optional[int] = None
    beat: Optional[float] = None
    note: Optional[Dict[str, Any]] = None
    value: Optional[Any] = None
    note_id: Optional[str] = None


class ScoreEditRequest(BaseModel):
    operations: List[ScoreOperation]


class ScoreExportRequest(BaseModel):
    format: Literal["midi", "png", "pdf"]
    page_size: Optional[str] = "A4"
    with_annotations: bool = True


class ScoreReExportRequest(BaseModel):
    page_size: Optional[str] = "A4"
    with_annotations: bool = True


class BeatDetectRequest(BaseModel):
    bpm_hint: Optional[int] = None
    sensitivity: Optional[float] = 0.5


class RhythmScoreRequest(BaseModel):
    reference_beats: List[float]
    user_beats: List[float]


class CommunityScorePublishRequest(BaseModel):
    score_id: str
    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_public: bool = True


class AudioLogRequest(BaseModel):
    file_name: str
    sample_rate: int
    duration: float
    params: Dict[str, Any] = Field(default_factory=dict)


class PitchCurveQuery(BaseModel):
    analysis_id: str
    mode: Optional[Literal["compare", "single"]] = "compare"


class ChordGenerationRequest(BaseModel):
    key: str = "C"
    tempo: int = 120
    style: str = "pop"
    melody: List[Dict[str, Any]] = Field(default_factory=list)


class VariationSuggestionRequest(BaseModel):
    score_id: str
    style: str = "traditional"
    difficulty: str = "medium"


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class HistoryCreateRequest(BaseModel):
    type: Literal["audio", "score", "report"]
    resource_id: str
    title: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReportExportRequest(BaseModel):
    analysis_id: str
    formats: List[Literal["pdf", "midi", "png"]]
    include_charts: bool = True
