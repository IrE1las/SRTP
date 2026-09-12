"""Interlocking exam API — standalone exercise for route-setting practice."""

import json
import csv
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from dotenv import dotenv_values
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.services import classic_exam_ai
from app.services.classic_exam_facts import EvidenceError, build_cards, load_evidence, route_summary, validate_inventory

router = APIRouter()

# ---- Paths to station data and rules (ai_design folder) ----
AI_DESIGN_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "ai_design"
STATION_DIR = AI_DESIGN_DIR / "station"
AI_DIR = AI_DESIGN_DIR / "ai"
KEY_ENV = AI_DIR / "key.env"
RULES_FILE = STATION_DIR / "interlocking_rules.md"
TABLE_FILE = STATION_DIR / "interlocking_table.csv"
TOPOLOGY_FILE = STATION_DIR / "station_topology.json"

# ---- Load DeepSeek API key ----
def _load_api_key() -> str:
    if settings.deepseek_api_key and not settings.deepseek_api_key.startswith("sk-xxxx"):
        return settings.deepseek_api_key
    if not KEY_ENV.exists():
        raise RuntimeError(f"API key file not found: {KEY_ENV}")
    value = dotenv_values(KEY_ENV).get('DEEPSEEK_API_KEY')
    if value and value.strip():
        return value.strip()
    raise RuntimeError("DEEPSEEK_API_KEY not found in key.env")

# ---- Correct answer for "由东郊方面至III股道的接车进路" (from interlocking_table.csv row 2) ----
CORRECT_ANSWER_III = {
    "route_name": "由东郊方面至III股道的接车进路",
    "route_buttons": ["XDLA", "SIIILA"],        # 排列进路按下按钮
    "switches": {                                 # 道岔: all normal position (定位)
        "5/7": "normal",
        "9/11": "normal",
        "13/15": "normal",
        "21": "normal",
        "23/25": "normal",
    },
    "hostile_signals": ["D11", "SIII"],           # 敌对信号
    "track_sections": ["7DG", "11-13DG", "21DG", "25DG", "IIIG"],  # 轨道区段
    "entry_signal": "XD",                         # 始端信号机
    "exit_signal": "SIII",                        # 终端信号机
    "direction": "接车",
    "aspect": "东郊方面",
    "destination": "III股道",
    "signal_display": "XD/U",                     # 信号机显示
}

# ---- Correct answer for "由东郊方面至I股道的接车进路" (from interlocking_table.csv row 3) ----
# CSV原文: 5/7，(13/15)，[9/11]，17/19，23/25
# §2括号约定: ()=反位, []=防护定位, {}=带动
# §4.1: (A/B)=路径上反位(侧向换股道), [A/B]=交叉渡线防护定位
CORRECT_ANSWER_I = {
    "route_name": "由东郊方面至I股道的接车进路",
    "route_buttons": ["XDLA", "D17LA"],           # I道终端为D17LA
    "switches": {
        "5/7": "normal",       # 定位 — 路径上直向通过
        "13/15": "reverse",    # 反位 — (13/15) 侧向通过，从III道换入I道
        "9/11": "normal",      # 定位 — [9/11] 防护道岔（与13/15交叉渡线，13/15反位时9/11锁定位防护）
        "17/19": "normal",     # 定位 — 路径上直向通过
        "23/25": "normal",     # 定位 — 路径上直向通过
    },
    "hostile_signals": ["D11", "D13", "D17"],     # 敌对信号
    "track_sections": ["7DG", "11-13DG", "9-15DG", "17-23DG", "IG"],  # 轨道区段
    "entry_signal": "XD",                         # 始端信号机
    "exit_signal": "D17",                         # 终端信号机（I道无出站信号机，用D17调车信号）
    "direction": "接车",
    "aspect": "东郊方面",
    "destination": "I股道",
    "signal_display": "XD/UU",                    # 信号机显示（双黄，经渡线侧向进I道）
}

# ---- Correct answer for "由东郊方面至4股道的接车进路" (from interlocking_table.csv row 4) ----
# CSV原文: 5/7，(13/15)，[9/11]，(17/19)，{23/25}，(27)
# §2括号约定: ()=反位, []=防护定位, {}=带动
# 教学重点: {23/25} 带动道岔——不在走行路径上，但随进路一起动作以提高效率
CORRECT_ANSWER_4 = {
    "route_name": "由东郊方面至4股道的接车进路",
    "route_buttons": ["XDLA", "S4LA"],            # 始端XDLA，终端S4LA（4道有出站信号机）
    "switches": {
        "5/7": "normal",       # 定位 — 路径上直向通过III道
        "13/15": "reverse",    # 反位 — (13/15) 侧向通过，从III道经渡线换入I道
        "9/11": "normal",      # 定位 — [9/11] 防护道岔（与13/15交叉渡线，13/15反位时9/11锁定位防护）
        "17/19": "reverse",    # 反位 — (17/19) 侧向通过，从I道继续侧向去往4道方向
        "23/25": "normal",     # 定位 — {23/25} 带动道岔★（不在列车走行主路径上，但为提高效率随进路一起动作）
        "27": "reverse",       # 反位 — (27) 侧向通过，最终渡线进入4道
    },
    "hostile_signals": ["D11", "D13", "S4"],      # 敌对信号
    "track_sections": ["7DG", "11-13DG", "9-15DG", "17-23DG", "19-27DG", "4G"],  # 轨道区段
    "entry_signal": "XD",                          # 始端信号机
    "exit_signal": "S4",                           # 终端信号机（4道出站信号机）
    "direction": "接车",
    "aspect": "东郊方面",
    "destination": "4股道",
    "signal_display": "XD/UU",                     # 信号机显示（双黄，经多处渡线侧向进4道）
}

# ---- Correct answer for "由北京方面发车由5股道的发车进路" (from interlocking_table.csv row 10) ----
# CSV原文: (1/3)、(9/11)、[13/15]、(21)
# §2括号约定: ()=反位, []=防护定位
# 教学重点: 条件区段 <23/25>25DG、<5/7>5DG — 道岔不在进路中但位置影响区段连通，须列入条件检查
# 23/25 固定为定位（非进路道岔），用于考察学生对条件区段的理解
CORRECT_ANSWER_BEIJING_DEPART_5 = {
    "route_name": "由北京方面发车由5股道的发车进路",
    "route_buttons": ["S5LA", "SLZA"],            # 始端S5LA，终端SLZA（上行列车终端按钮）
    "switches": {
        "1/3": "reverse",      # 反位 — (1/3) 侧向通过，从I道经渡线去往北京方向
        "9/11": "reverse",     # 反位 — (9/11) 侧向通过，从III道经渡线换入I道
        "13/15": "normal",     # 定位 — [13/15] 防护道岔（与9/11交叉渡线，9/11反位时13/15锁定位防护）
        "21": "reverse",       # 反位 — (21) 侧向通过，从5道经渡线换入III道
        # 注意：23/25 不在此列！23/25 不是本进路的道岔，仅在条件区段 <23/25>25DG 中出现
    },
    "hostile_signals": ["D1", "D7", "D9", "S5D"],  # 敌对信号
    "track_sections": [                              # 轨道区段（含条件区段，用纯区段名便于比对）
        "21DG", "11-13DG", "9-15DG", "3DG", "1DG", "IIAG",  # 无条件区段
        "25DG", "5DG",                                         # 条件区段（学生界面选纯区段名，AI 据题目条件解释为 <23/25>25DG、<5/7>5DG）
    ],
    "entry_signal": "S5",                          # 始端信号机（5道出站）
    "exit_signal": "SLZ",                          # 终端（上行列车终端，非具体信号机）
    "direction": "发车",
    "aspect": "北京方面",
    "destination": "5股道",
    "signal_display": "S5/L或U或LU",               # 信号机显示（自动闭塞多显示）
}

# Map route_type to correct answer
CORRECT_ANSWERS = {
    "dongjiao_to_III": CORRECT_ANSWER_III,
    "dongjiao_to_I": CORRECT_ANSWER_I,
    "dongjiao_to_4": CORRECT_ANSWER_4,
    "beijing_depart_5": CORRECT_ANSWER_BEIJING_DEPART_5,
}


# ---- Request / Response schemas ----
RouteType = Literal['dongjiao_to_III', 'dongjiao_to_I', 'dongjiao_to_4', 'beijing_depart_5']
DeviceCode = Annotated[str, Field(min_length=1, max_length=40)]


class ExamSubmission(BaseModel):
    route_buttons: list[DeviceCode] = Field(default_factory=list, max_length=40)
    switches: dict[DeviceCode, Literal['normal', 'reverse']] = Field(default_factory=dict, max_length=8)
    hostile_signals: list[DeviceCode] = Field(default_factory=list, max_length=40)
    track_sections: list[DeviceCode] = Field(default_factory=list, max_length=40)
    route_type: RouteType = 'dongjiao_to_III'


class ExamResult(BaseModel):
    all_correct: bool
    message: str
    details: dict = {}
    ai_explanation: str = ""


class AiExplainRequest(ExamSubmission):
    """Request to trigger AI explanation for a previously-submitted answer."""
    # Legacy clients may send errors; they are never trusted for grading or prompting.
    errors: dict = Field(default_factory=dict)


class AiExplainResponse(BaseModel):
    ai_explanation: str
    source: Literal['ai', 'rules_fallback', 'no_errors']
    items: list[dict] = Field(default_factory=list)
    route_summary: str = ''
    message: str = ''
    retryable: bool = False
    reason_code: str | None = None
    request_id: str = ''
    cached: bool = False


# ---- Helper: load rules text ----
def _load_rules() -> str:
    if not RULES_FILE.exists():
        return ""
    with open(RULES_FILE, encoding="utf-8") as f:
        return f.read()


# ---- Helper: load topology JSON for context ----
def _load_topology() -> dict:
    if not TOPOLOGY_FILE.exists():
        return {}
    with open(TOPOLOGY_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---- Core: compare student answer vs correct answer ----
def _compare_answers(student: ExamSubmission) -> dict:
    """Compare student submission with correct answer, return error details."""
    correct = CORRECT_ANSWERS.get(student.route_type, CORRECT_ANSWER_III)
    errors = {
        "route_buttons": {"missing": [], "extra": [], "correct": correct["route_buttons"]},
        "switches": {"wrong_position": [], "missing": [], "extra": [], "correct": correct["switches"]},
        "hostile_signals": {"missing": [], "extra": [], "correct": correct["hostile_signals"]},
        "track_sections": {"missing": [], "extra": [], "correct": correct["track_sections"]},
    }

    # --- Route buttons ---
    correct_buttons = set(correct["route_buttons"])
    student_buttons = set(student.route_buttons)
    errors["route_buttons"]["missing"] = sorted(correct_buttons - student_buttons)
    errors["route_buttons"]["extra"] = sorted(student_buttons - correct_buttons)

    # --- Switches ---
    correct_switches = correct["switches"]
    for sw, expected_pos in correct_switches.items():
        if sw not in student.switches:
            errors["switches"]["missing"].append(sw)
        elif student.switches[sw] != expected_pos:
            errors["switches"]["wrong_position"].append({
                "switch": sw,
                "expected": expected_pos,
                "student": student.switches[sw],
            })
    for sw in student.switches:
        if sw not in correct_switches:
            errors["switches"]["extra"].append(sw)

    # --- Hostile signals ---
    correct_signals = set(correct["hostile_signals"])
    student_signals = set(student.hostile_signals)
    errors["hostile_signals"]["missing"] = sorted(correct_signals - student_signals)
    errors["hostile_signals"]["extra"] = sorted(student_signals - correct_signals)

    # --- Track sections ---
    correct_sections = set(correct["track_sections"])
    student_sections = set(student.track_sections)
    errors["track_sections"]["missing"] = sorted(correct_sections - student_sections)
    errors["track_sections"]["extra"] = sorted(student_sections - correct_sections)

    return errors


def _is_all_correct(errors: dict) -> bool:
    """Check if all categories have zero errors."""
    for category in errors.values():
        for key, val in category.items():
            if key == "correct":
                continue
            if isinstance(val, list) and len(val) > 0:
                return False
    return True


def _build_student_summary(student: ExamSubmission) -> str:
    """Build a readable summary of the student's submission."""
    lines = ["【学生办理的进路】"]
    lines.append(f"排列进路按下按钮：{', '.join(student.route_buttons) if student.route_buttons else '（未选择）'}")
    if student.switches:
        sw_parts = []
        for sw, pos in student.switches.items():
            pos_cn = "定位" if pos == "normal" else "反位"
            sw_parts.append(f"{sw}({pos_cn})")
        lines.append(f"道岔设置：{'、'.join(sw_parts)}")
    else:
        lines.append("道岔设置：（未设置）")
    lines.append(f"敌对信号（设为红色）：{', '.join(student.hostile_signals) if student.hostile_signals else '（未选择）'}")
    lines.append(f"轨道区段（选中）：{', '.join(student.track_sections) if student.track_sections else '（未选择）'}")
    return "\n".join(lines)


def _build_error_summary(errors: dict) -> str:
    """Build a readable error summary for the AI."""
    lines = ["【错误汇总】"]

    # Route buttons
    rb = errors["route_buttons"]
    if rb["missing"] or rb["extra"]:
        parts = []
        if rb["missing"]:
            parts.append(f"漏选按钮：{'、'.join(rb['missing'])}")
        if rb["extra"]:
            parts.append(f"多选按钮：{'、'.join(rb['extra'])}")
        lines.append(f"排列进路按钮 — {', '.join(parts)}；正确答案应为：{'、'.join(rb['correct'])}")

    # Switches
    sw = errors["switches"]
    if sw["missing"] or sw["extra"] or sw["wrong_position"]:
        parts = []
        if sw["missing"]:
            parts.append(f"漏设置道岔：{'、'.join(sw['missing'])}")
        if sw["extra"]:
            parts.append(f"多设置道岔：{'、'.join(sw['extra'])}")
        if sw["wrong_position"]:
            wp_parts = [f"{w['switch']}(你选了{'定位' if w['student'] == 'normal' else '反位'}，应为{'定位' if w['expected'] == 'normal' else '反位'})" for w in sw["wrong_position"]]
            parts.append(f"道岔位置错误：{'、'.join(wp_parts)}")
        lines.append(f"道岔 — {', '.join(parts)}")

    # Hostile signals
    hs = errors["hostile_signals"]
    if hs["missing"] or hs["extra"]:
        parts = []
        if hs["missing"]:
            parts.append(f"漏封锁：{'、'.join(hs['missing'])}")
        if hs["extra"]:
            parts.append(f"多封锁：{'、'.join(hs['extra'])}")
        lines.append(f"敌对信号 — {', '.join(parts)}；正确答案应为：{'、'.join(hs['correct'])}")

    # Track sections
    ts = errors["track_sections"]
    if ts["missing"] or ts["extra"]:
        parts = []
        if ts["missing"]:
            parts.append(f"漏选：{'、'.join(ts['missing'])}")
        if ts["extra"]:
            parts.append(f"多选：{'、'.join(ts['extra'])}")
        lines.append(f"轨道区段 — {', '.join(parts)}；正确答案应为：{'、'.join(ts['correct'])}")

    return "\n".join(lines)


def _load_interlocking_table_row(route_type: str) -> str:
    """Load the interlocking table CSV and return the matching row as readable text."""
    if not TABLE_FILE.exists():
        return ""
    try:
        # Try UTF-8 first, then GBK
        content = None
        for enc in ['utf-8', 'gbk']:
            try:
                with open(TABLE_FILE, encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        if not content:
            return ""

        lines = content.strip().split('\n')
        if len(lines) < 2:
            return ""

        header = lines[0]
        # Route type → CSV row mapping (approximate: search by key terms)
        route_map = {
            "dongjiao_to_III": ("东郊", "III"),
            "dongjiao_to_I": ("东郊", "I"),
            "dongjiao_to_4": ("东郊", "4"),
            "beijing_depart_5": ("北京", "5"),
        }
        search = route_map.get(route_type)
        if not search:
            return ""

        matching_rows = []
        direction = "发车" if route_type == "beijing_depart_5" else "接车"
        destination = ("由" if direction == "发车" else "至") + search[1] + "股道"
        for line in lines[1:]:
            values = next(csv.reader([line]))
            if search[0] in values[0] and direction in values[0] and values[1].strip() == destination:
                matching_rows.append(line)

        if not matching_rows:
            return ""

        # Build readable output
        cols = header.split(',')
        result = ["【联锁表原文（标准答案）】"]
        for row in matching_rows:
            vals = row.split(',')
            parts = []
            for i, (col, val) in enumerate(zip(cols, vals)):
                if val.strip():
                    parts.append(f"{col.strip()}：{val.strip()}")
            result.append(" | ".join(parts))
        return "\n".join(result)
    except Exception:
        return ""


def _build_problem_conditions(route_type: str) -> str:
    """Build explicit problem conditions for the AI."""
    conditions = {
        "dongjiao_to_III": "无特殊题目条件，正常办理接车进路。",
        "dongjiao_to_I": "无特殊题目条件，正常办理接车进路。注意I道无出站信号机，终端按钮为D17LA。",
        "dongjiao_to_4": "无特殊题目条件，正常办理接车进路。",
        "beijing_depart_5": "★ 23/25号道岔固定为定位，5/7号道岔固定为定位。这两个道岔不是进路道岔（不在道岔列），仅作为已知条件影响轨道区段的判断。",
    }
    return conditions.get(route_type, "无特殊题目条件。")


def _call_ai_for_explanation(errors: dict, student: ExamSubmission, cache_scope: str = '') -> dict:
    """Publish only explanations backed by the same local sources as grading."""
    try:
        evidence = load_evidence(student.route_type, CORRECT_ANSWERS[student.route_type])
        validate_inventory(student, evidence)
        cards = build_cards(errors, student, evidence)
        route = route_summary(evidence)
    except EvidenceError:
        raise HTTPException(status_code=503, detail='本题解释依据暂时不完整或不一致，请联系教师检查题库；本次判分仍可查看。') from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return classic_exam_ai.explain(
        cards, route, settings.deepseek_model, settings.deepseek_base_url,
        _load_api_key, cache_scope, evidence['fingerprint'],
    )

# ---- API endpoints ----
@router.post("/exam/submit", response_model=ExamResult)
def submit_exam(
    submission: ExamSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamResult:
    """Step 1: Fast local comparison — no AI call. Returns right/wrong + error details."""
    errors = _compare_answers(submission)
    all_correct = _is_all_correct(errors)

    if all_correct:
        route_name = CORRECT_ANSWERS.get(submission.route_type, CORRECT_ANSWER_III)["route_name"]
        return ExamResult(
            all_correct=True,
            message=f"🎉 全部正确！你成功办理了{route_name}。按钮、道岔、敌对信号和轨道区段的选择完全符合联锁表要求。",
            details={"correct_answer": CORRECT_ANSWERS.get(submission.route_type, CORRECT_ANSWER_III)},
            ai_explanation="",
        )
    else:
        return ExamResult(
            all_correct=False,
            message="❌ 办理有误，请查看下方错误详情。如需 AI 分析错误原因，请点击「AI 解析」按钮。",
            details={
                "errors": errors,
                "correct_answer": CORRECT_ANSWERS.get(submission.route_type, CORRECT_ANSWER_III),
            },
            ai_explanation="",
        )


@router.post("/exam/ai-explain", response_model=AiExplainResponse)
def ai_explain(
    request: AiExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiExplainResponse:
    """Step 2: Student clicks「AI 解析」→ call DeepSeek to explain WHY each error is wrong."""
    student = ExamSubmission(
        route_buttons=request.route_buttons,
        switches=request.switches,
        hostile_signals=request.hostile_signals,
        track_sections=request.track_sections,
        route_type=request.route_type,
    )
    errors = _compare_answers(student)
    explanation = _call_ai_for_explanation(errors, student, cache_scope=str(current_user.id))
    return AiExplainResponse(**explanation)

