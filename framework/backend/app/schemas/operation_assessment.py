from pydantic import Field, StrictBool, StrictInt
from app.schemas.operation import Body


class AssessmentDraft(Body):
    revision: StrictInt = Field(ge=0)
    enabled: StrictBool = False
    route_ids: list[str] = Field(default_factory=list, max_length=10)
    wrong_signal_cap: StrictBool = False
    confirmed: StrictBool = False


class AssessmentReview(Body):
    evaluation_id: StrictInt = Field(gt=0)
    grade_revision: StrictInt = Field(ge=1)
    reason: str = Field(default='', max_length=2000)
