"""Schemas for generated original-station shunting questions."""

from typing import Literal

from pydantic import BaseModel, Field


class ShuntingAnswerSubmission(BaseModel):
    """Student answer for the four source-table answer categories."""

    route_buttons: list[str] = Field(default_factory=list, max_length=100)
    switches: dict[str, Literal["normal", "reverse"]] = Field(default_factory=dict, max_length=100)
    switch_roles: dict[str, Literal["required", "protective", "driven"]] = Field(default_factory=dict, max_length=100)
    hostile_signals: list[str] = Field(default_factory=list, max_length=100)
    track_sections: list[str] = Field(default_factory=list, max_length=100)
