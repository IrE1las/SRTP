"""Validate precision before conversion; never silently round a submitted score."""
from decimal import Decimal, InvalidOperation
from pydantic import Field, StrictInt, field_validator
from app.schemas.operation import Body


class GradeRevision(Body):
    revision: StrictInt = Field(ge=0)


class GradeDraft(GradeRevision):
    score: Decimal | None = None
    comment: str | None = Field(default=None, max_length=4000)

    @field_validator('score', mode='before')
    @classmethod
    def exact_score(cls, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError('成绩须为0—100的数字，最多两位小数')
        try:
            score = Decimal(str(value))
        except InvalidOperation:
            raise ValueError('成绩须为0—100的数字，最多两位小数') from None
        if not score.is_finite() or score < 0 or score > 100 or score.as_tuple().exponent < -2:
            raise ValueError('成绩须为0—100的数字，最多两位小数')
        return score
