from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, StrictBool, StrictInt
from app.schemas.operation import Body


class ExamDraft(Body):
    name: str | None = Field(default=None, max_length=200)
    classes: list[str] = Field(default_factory=list, max_length=100)
    version_id: StrictInt | None = Field(default=None, gt=0)
    opens_at: AwareDatetime | None = None
    closes_at: AwareDatetime | None = None
    duration_minutes: StrictInt | None = Field(default=None, gt=0, le=10080)


class ExamEdit(ExamDraft):
    revision: StrictInt = Field(ge=1)


class Revision(Body):
    revision: StrictInt = Field(ge=1)


class Begin(Body):
    fullscreen: StrictBool


class ControlEvent(Body):
    event_id: UUID
    kind: Literal['exit', 'restore']
    occurred_at: AwareDatetime


class Sync(Body):
    fullscreen: StrictBool
    events: list[ControlEvent] = Field(default_factory=list, max_length=500)


class Submit(Body):
    expected_sequence: StrictInt = Field(ge=0)
