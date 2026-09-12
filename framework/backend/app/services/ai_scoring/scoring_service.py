"""DeepSeek-compatible scoring service with local fallback."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_score import AiScore
from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.models.operation_log import OperationLog

PLACEHOLDER_KEYS = {"", "sk-xxxxxxxxx", "your-deepseek-api-key"}


def generate_ai_score(db: Session, session_id: int) -> AiScore:
    """Generate or update a score for a completed session."""

    session = db.get(ExerciseSession, session_id)
    if session is None:
        raise ValueError("练习会话不存在")
    exercise = db.get(Exercise, session.exercise_id)
    if exercise is None:
        raise ValueError("练习题不存在")
    if session.status == "ongoing":
        raise ValueError("练习尚未结束，不能生成评分")

    logs = (
        db.query(OperationLog)
        .filter(OperationLog.session_id == session_id)
        .order_by(OperationLog.sequence_no)
        .all()
    )
    result = _local_score(session, exercise, logs)
    score = db.query(AiScore).filter(AiScore.session_id == session_id).first()
    if score is None:
        score = AiScore(session_id=session_id, **result)
        db.add(score)
    else:
        for key, value in result.items():
            setattr(score, key, value)
    db.commit()
    db.refresh(score)
    return score


def get_ai_score(db: Session, session_id: int) -> AiScore | None:
    """Return score by session ID."""

    return db.query(AiScore).filter(AiScore.session_id == session_id).first()


def list_user_scores(db: Session, student_id: int) -> list[AiScore]:
    """Return scores for sessions owned by a student."""

    return (
        db.query(AiScore)
        .join(ExerciseSession, ExerciseSession.id == AiScore.session_id)
        .filter(ExerciseSession.student_id == student_id)
        .order_by(AiScore.created_at.desc(), AiScore.id.desc())
        .all()
    )


def _local_score(session: ExerciseSession, exercise: Exercise, logs: list[OperationLog]) -> dict:
    failed_logs = [log for log in logs if log.operation_result != "success"]
    invalid_rate = session.invalid_clicks / session.total_clicks if session.total_clicks else 0
    completion_bonus = 40 if session.completion_status == "success" else 20
    accuracy_score = max(0, completion_bonus - len(failed_logs) * 5)

    total_time = session.total_time or exercise.time_limit
    if total_time <= exercise.time_limit:
        efficiency_score = 30
    else:
        overtime_blocks = (total_time - exercise.time_limit + 29) // 30
        efficiency_score = max(0, 30 - overtime_blocks * 3)

    operation_quality = max(0, 30 - int(invalid_rate * 50) - len(failed_logs) * 2)
    total_score = round(accuracy_score + efficiency_score + operation_quality, 2)

    wrong_operations = [
        {
            "sequence_no": log.sequence_no,
            "operation": log.operation_type,
            "target": log.target_code,
            "error": log.error_message or "操作未成功",
        }
        for log in failed_logs
    ]
    suggestions = []
    if session.completion_status != "success":
        suggestions.append("请先确认目标进路的始端和终端信号机，再按联锁表顺序办理。")
    if invalid_rate > 0:
        suggestions.append("减少无效点击，操作前先核对道岔、区段和敌对进路状态。")
    if total_time > exercise.time_limit:
        suggestions.append("注意练习限时，熟悉标准进路后再提高操作速度。")
    if not suggestions:
        suggestions.append("本次操作流程较规范，可继续练习敌对进路和异常处置。")

    key = settings.deepseek_api_key or ""
    mode = "local_fallback" if key in PLACEHOLDER_KEYS or key.startswith("sk-xxxx") else "deepseek_placeholder"
    return {
        "accuracy_score": float(accuracy_score),
        "efficiency_score": float(efficiency_score),
        "operation_quality": float(operation_quality),
        "total_score": float(total_score),
        "ai_comment": _build_comment(session, total_score, failed_logs),
        "wrong_operations": wrong_operations,
        "suggestions": suggestions,
        "deepseek_response": {
            "mode": mode,
            "message": "DeepSeek API key 为占位符，当前使用本地规则评分。",
        },
    }


def _build_comment(session: ExerciseSession, total_score: float, failed_logs: list[OperationLog]) -> str:
    if session.completion_status == "success" and not failed_logs:
        return f"本次练习目标进路办理正确，操作规范，总分 {total_score} 分。"
    if session.completion_status == "timeout":
        return f"本次练习超时结束，总分 {total_score} 分。建议加强标准进路办理流程训练。"
    return f"本次练习存在 {len(failed_logs)} 次异常或无效操作，总分 {total_score} 分。请结合回放复盘。"
