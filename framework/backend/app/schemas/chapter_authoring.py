"""Teacher-authored chapter questions; only explicit answers authorize grading."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr


class ChapterDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    chapter: StrictInt = Field(ge=1, le=6)
    kind: Literal['choice', 'multi', 'true_false', 'cell']
    stem: StrictStr = Field(min_length=1, max_length=10000)
    options: list[StrictStr] = Field(default_factory=list, max_length=12)
    answer: StrictBool | StrictStr | list[StrictStr]
    accepted: list[list[StrictStr]] = Field(default_factory=list, max_length=20)
    explanation: StrictStr = Field(default='', max_length=10000)
    source_reference: StrictStr = Field(min_length=1, max_length=1500)


class ChapterEdit(ChapterDraft):
    revision: StrictInt = Field(ge=0)
