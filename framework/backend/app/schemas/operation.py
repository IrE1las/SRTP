from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Initial(Body):
    interval_available: bool = True
    occupied_sections: list[str] = Field(default_factory=list, max_length=100)


class Draft(Body):
    title: str | None = Field(default=None, max_length=200)
    prompt: str | None = Field(default=None, max_length=20000)
    classes: list[str] = Field(default_factory=list, max_length=100)
    initial: Initial = Field(default_factory=Initial)


class UpdateDraft(Draft):
    revision: StrictInt = Field(ge=1)


class StartSession(Body):
    kind: Literal['recording', 'preview']


class Click(Body):
    event_id: UUID
    sequence: StrictInt = Field(ge=1)
    action: Literal['function', 'target', 'button', 'cancel_selection']
    button_id: str | None = Field(default=None, max_length=80)
    target_id: str | None = Field(default=None, max_length=80)
    target_kind: Literal['signal', 'switch', 'section', 'block'] | None = None
    parameters: dict = Field(default_factory=dict, max_length=0)
    pin: str | None = Field(default=None, max_length=32, repr=False)

    @model_validator(mode='after')
    def required_action_fields(self):
        if self.action in {'function', 'button'} and not self.button_id:
            raise ValueError('按钮动作必须包含按钮ID')
        if self.action == 'target' and (not self.target_id or not self.target_kind):
            raise ValueError('目标动作必须包含目标ID和类型')
        return self
