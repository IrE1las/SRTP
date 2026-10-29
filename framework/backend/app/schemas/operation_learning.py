from pydantic import Field, StrictInt
from app.schemas.operation import Body


class Begin(Body):
    restart_from: str | None = Field(default=None, max_length=36)


class Review(Body):
    revision: StrictInt = Field(ge=0)
    comment: str | None = Field(default=None, max_length=6000)
    confirmed: bool = False
