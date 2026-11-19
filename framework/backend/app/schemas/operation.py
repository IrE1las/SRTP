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
    action: Literal['function', 'target', 'button', 'cancel_selection', 'command']
    button_id: str | None = Field(default=None, max_length=80)
    target_id: str | None = Field(default=None, max_length=80)
    target_kind: Literal['signal', 'switch', 'section', 'block'] | None = None
    parameters: dict = Field(default_factory=dict, max_length=5)
    pin: str | None = Field(default=None, max_length=32, repr=False)

    @model_validator(mode='after')
    def required_action_fields(self):
        if self.action in {'function', 'button', 'command'} and not self.button_id:
            raise ValueError('按钮动作必须包含按钮ID')
        if self.action == 'target' and (not self.target_id or not self.target_kind):
            raise ValueError('目标动作必须包含目标ID和类型')
        if self.action == 'command' and (not self.target_id or not self.target_kind):
            raise ValueError('设备命令必须包含目标ID和类型')
        if self.action != 'command' and self.parameters:
            raise ValueError('仅设备命令可包含操作参数')
        if self.action == 'command':
            if 'position' in self.parameters and (type(self.parameters['position']) is not int or self.parameters['position'] not in (0,1)):
                raise ValueError('道岔恢复位置须为定位或反位')
            if 'kind' in self.parameters and self.parameters['kind'] not in ('vehicle','fault'):
                raise ValueError('区段输入须为车辆或故障占用')
            if any(not isinstance(self.parameters[k],str) or not 1<=len(self.parameters[k])<=80
                   for k in ('signal','route_instance_id') if k in self.parameters):
                raise ValueError('信号和进路目标格式不正确')
        return self
