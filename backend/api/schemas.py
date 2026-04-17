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
    reference_id: Optional[str] = None
    user_recording_id: Optional[str] = None
    reference_pitch_path: Optional[str] = None
    user_pitch_path: Optional[str] = None
    reference_pitch_sequence: Optional[List[PitchSequenceItem]] = None
    user_pitch_sequence: Optional[List[PitchSequenceItem]] = None
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
    language: str = Field("en", description="Language for feedback ('en' or 'zh')")
    scoring_model: str = Field("balanced", description="Scoring model: 'strict', 'balanced', or 'lenient'")
    threshold_ms: float = Field(50.0, description="Time window for on-time classification (ms)")


class AnalyzeRhythmRequest(BaseModel):
    """Request for end-to-end rhythm audio analysis.
    
    Supports multilingual feedback and flexible scoring models.
    """
    language: str = Field("en", description="Language for feedback ('en' or 'zh')")
    scoring_model: str = Field("balanced", description="Scoring model: 'strict', 'balanced', or 'lenient'")
    threshold_ms: float = Field(50.0, description="Time window for on-time classification (ms)")


class CommunityScorePublishRequest(BaseModel):
    score_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    style: Optional[str] = None
    instrument: Optional[str] = None
    price: Optional[float] = Field(default=0.0, ge=0)
    cover_url: Optional[str] = None
    subtitle: Optional[str] = None
    author_name: Optional[str] = None
    source_file_name: Optional[str] = None
    is_public: bool = True


class CommunityCommentCreateRequest(BaseModel):
    content: str
    username: Optional[str] = None
    avatar_url: Optional[str] = None


class AudioLogRequest(BaseModel):
    file_name: str
    sample_rate: int
    duration: float
    analysis_id: Optional[str] = None
    channels: Optional[int] = None
    frame_count: Optional[int] = None
    byte_size: Optional[int] = None
    audio_format: Optional[str] = None
    file_extension: Optional[str] = None
    subtype: Optional[str] = None
    source: str = "api"
    stage: str = "manual"
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


class PreferencesUpdateRequest(BaseModel):
    audio_engine: Optional[str] = None
    export_formats: Optional[List[str]] = None


class UserUpdatePayload(BaseModel):
    """个人资料更新请求体"""
    nickname: Optional[str] = None
    bio: Optional[str] = None
    birthday: Optional[str] = None
    music_taste: Optional[List[str]] = None
    avatar: Optional[str] = None
