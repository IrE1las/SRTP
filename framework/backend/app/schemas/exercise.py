"""Exercise, session and operation-log schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.interlocking import StationSnapshotResponse
from app.schemas.station import StationDetailResponse

Difficulty = Literal["easy", "medium", "hard"]
ExerciseType = Literal["route_arrange", "signal_practice", "troubleshooting"]
SessionStatus = Literal["ongoing", "completed", "timeout", "aborted"]
CompletionStatus = Literal["success", "failed", "timeout"]


class TargetRoute(BaseModel):
    """Expected route target for an exercise."""

    entry_signal: str = Field(min_length=1, max_length=20)
    exit_signal: str = Field(min_length=1, max_length=20)
    route_name: str | None = Field(default=None, max_length=100)


class ExerciseCreateRequest(BaseModel):
    """Teacher request to create an exercise."""

    station_id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    exercise_type: ExerciseType = "route_arrange"
    target_routes: list[TargetRoute] = Field(min_length=1)
    time_limit: int = Field(default=600, ge=30, le=7200)
    difficulty: Difficulty = "easy"
    scoring_rules: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ExerciseUpdateRequest(BaseModel):
    """Teacher request to update an exercise."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    exercise_type: ExerciseType | None = None
    target_routes: list[TargetRoute] | None = None
    time_limit: int | None = Field(default=None, ge=30, le=7200)
    difficulty: Difficulty | None = None
    scoring_rules: dict[str, Any] | None = None
    is_active: bool | None = None


class ExerciseResponse(BaseModel):
    """Exercise response."""

    id: int
    teacher_id: int
    station_id: int
    title: str
    description: str | None
    exercise_type: str
    target_routes: list[dict[str, Any]]
    time_limit: int
    difficulty: str
    scoring_rules: dict[str, Any]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExerciseLobbyItemResponse(ExerciseResponse):
    """Exercise item shown in the student lobby."""


class ExerciseDetailResponse(ExerciseResponse):
    """Full exercise detail."""


class ExerciseSessionStartRequest(BaseModel):
    """Request to start an exercise session."""

    exercise_id: int


class ExerciseSessionFinishRequest(BaseModel):
    """Request to finish an exercise session manually."""

    reason: str = Field(default="aborted", max_length=50)


class ExerciseSessionResponse(BaseModel):
    """Exercise session response."""

    id: int
    student_id: int
    exercise_id: int
    station_id: int
    start_time: datetime
    end_time: datetime | None
    total_time: int | None
    total_clicks: int
    valid_clicks: int
    invalid_clicks: int
    status: str
    completion_status: str | None
    final_snapshot: dict[str, Any] | None
    result_summary: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExerciseStartResponse(BaseModel):
    """Payload returned when a session starts."""

    exercise: ExerciseDetailResponse
    session: ExerciseSessionResponse
    station_detail: StationDetailResponse
    snapshot: StationSnapshotResponse
    deadline_at: datetime


class OperationLogResponse(BaseModel):
    """Operation log response."""

    id: int
    session_id: int
    timestamp: datetime
    sequence_no: int
    operation_type: str
    target_code: str
    target_type: str
    operation_result: str
    request_payload: dict[str, Any]
    state_before: dict[str, Any]
    state_after: dict[str, Any]
    error_message: str | None
    time_spent_ms: int

    model_config = ConfigDict(from_attributes=True)


class ExerciseReplayResponse(BaseModel):
    """Exercise replay payload."""

    session: ExerciseSessionResponse
    exercise: ExerciseDetailResponse
    logs: list[OperationLogResponse]


class ExerciseRuntimeRouteRequest(BaseModel):
    """Session-scoped route arrangement request."""

    session_id: int
    entry_signal: str = Field(min_length=1, max_length=20)
    exit_signal: str = Field(min_length=1, max_length=20)


class ExerciseRuntimeSwitchRequest(BaseModel):
    """Session-scoped switch operation request."""

    session_id: int
    switch_code: str = Field(min_length=1, max_length=20)
    target_position: Literal["normal", "reverse"]


class ExerciseRuntimeSectionRequest(BaseModel):
    """Session-scoped section occupancy request."""

    session_id: int
    section_code: str = Field(min_length=1, max_length=20)
    occupied: bool


class ExerciseRuntimeSignalRequest(BaseModel):
    """Session-scoped route cancel request."""

    session_id: int
    signal_code: str = Field(min_length=1, max_length=20)


class ExerciseRuntimeUnlockRequest(BaseModel):
    """Session-scoped manual unlock request."""

    session_id: int
    section_code: str = Field(min_length=1, max_length=20)


class ExerciseRuntimeResponse(BaseModel):
    """Response for a session-scoped runtime operation."""

    success: bool
    message: str
    snapshot: StationSnapshotResponse
    session: ExerciseSessionResponse
