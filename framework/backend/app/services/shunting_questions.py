"""Question generation and answer checking for the reviewed shunting table."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.models.shunting_route import ShuntingDataset, ShuntingQuestion, ShuntingRoute
from app.services.shunting_data import DATASET_KEY

QUESTION_VERSION = 1
QUESTION_TYPE = "route_interlocking"
_SWITCH_RE = re.compile(r"(?P<opening>[\(\[\{]?)(?P<code>\d+(?:/\d+)?)(?P<closing>[\)\]\}]?)")


def get_dataset(db: Session) -> ShuntingDataset:
    dataset = db.query(ShuntingDataset).filter_by(dataset_key=DATASET_KEY).one_or_none()
    if dataset is None:
        raise ValueError("尚未导入原始图车站调车联锁表")
    return dataset


def _tokens(value: str | None) -> list[str]:
    if not value:
        return []
    return [token.strip() for token in re.split(r"[、,\n\r]+", value) if token.strip()]


def _sort_key(value: str) -> tuple[Any, ...]:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value))


def parse_switches(value: str | None) -> list[dict[str, str]]:
    """Parse the source notation while preserving position and bracket role.

    Parentheses mean reverse position. Square and curly brackets identify the
    source's protective and driven categories; they do not change position.
    """

    parsed: list[dict[str, str]] = []
    for match in _SWITCH_RE.finditer(value or ""):
        opening = match.group("opening")
        closing = match.group("closing")
        if opening and closing and {opening, closing} not in ({"(", ")"}, {"[", "]"}, {"{", "}"}):
            continue
        role = "driven" if opening == "{" or closing == "}" else "protective" if opening == "[" or closing == "]" else "required"
        parsed.append({
            "code": match.group("code"),
            "position": "reverse" if opening == "(" or closing == ")" else "normal",
            "role": role,
            "notation": match.group(0),
        })
    return parsed


def _conditional_tokens(value: str | None) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for raw in _tokens(value):
        match = re.match(r"^<([^>]+)>(.*)$", raw)
        result.append({
            "raw": raw,
            "code": match.group(2) if match else raw,
            "condition": match.group(1) if match else None,
        })
    return result


def build_answer_spec(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_buttons": _tokens(fields.get("排列进路按下按钮")),
        "switches": parse_switches(fields.get("道岔")),
        "hostile_signals": _conditional_tokens(fields.get("敌对信号")),
        "track_sections": _conditional_tokens(fields.get("轨道区段")),
    }


def _answer_values(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_buttons": list(spec.get("route_buttons", [])),
        "switches": {
            item["code"]: item["position"]
            for item in spec.get("switches", [])
            if item.get("code") and item.get("position")
        },
        "switch_roles": {
            item["code"]: item["role"]
            for item in spec.get("switches", [])
            if item.get("code") and item.get("role")
        },
        "hostile_signals": [item["raw"] for item in spec.get("hostile_signals", [])],
        "track_sections": [item["raw"] for item in spec.get("track_sections", [])],
    }


def _options(routes: Iterable[ShuntingRoute]) -> dict[str, Any]:
    button_values: set[str] = set()
    switch_values: set[str] = set()
    hostile_values: set[str] = set()
    section_values: set[str] = set()
    for route in routes:
        spec = build_answer_spec(route.fields)
        button_values.update(spec["route_buttons"])
        switch_values.update(item["code"] for item in spec["switches"])
        hostile_values.update(item["raw"] for item in spec["hostile_signals"])
        section_values.update(item["raw"] for item in spec["track_sections"])
    return {
        "route_buttons": sorted(button_values, key=_sort_key),
        "switches": sorted(switch_values, key=_sort_key),
        "switch_roles": ["required", "protective", "driven"],
        "hostile_signals": sorted(hostile_values, key=_sort_key),
        "track_sections": sorted(section_values, key=_sort_key),
    }


def _difficulty(spec: dict[str, Any]) -> str:
    complexity = len(spec["switches"]) + len(spec["hostile_signals"]) + len(spec["track_sections"])
    if complexity <= 8:
        return "easy"
    if complexity <= 12:
        return "medium"
    return "hard"


def _question_values(route: ShuntingRoute, options: dict[str, Any]) -> dict[str, Any]:
    fields = route.fields
    spec = build_answer_spec(fields)
    direction = fields["方向"]
    route_label = fields["进路"]
    return {
        "question_key": f"{DATASET_KEY}:{route.route_number}:v{QUESTION_VERSION}",
        "question_type": QUESTION_TYPE,
        "title": f"{route.route_number}号调车进路：{direction}{route_label}",
        "prompt": (
            f"请根据原始图车站的设备关系，完成{route.route_number}号“{direction}{route_label}”调车进路。"
            "请选择排列进路按钮、各号道岔的位置及作用类别、敌对信号和需要检查的轨道区段。"
            "原表中的括号、方括号、大括号及尖括号条件均按原记号理解；提交后系统会指出漏选、多选和错选。"
        ),
        "difficulty": _difficulty(spec),
        "answer_spec": spec,
        "options": options,
        "source_snapshot": {
            "dataset_key": DATASET_KEY,
            "route_id": route.id,
            "route_number": route.route_number,
            "direction": direction,
            "route": route_label,
            "source_excel_row": route.provenance.get("excel_row"),
        },
        "is_active": True,
    }


def generate_shunting_questions(db: Session) -> dict[str, int]:
    """Create or refresh one deterministic question for each imported route."""

    dataset = get_dataset(db)
    routes = db.query(ShuntingRoute).filter_by(dataset_id=dataset.id).order_by(ShuntingRoute.route_number).all()
    if not routes:
        raise ValueError("原始图车站没有可生成题目的调车进路")
    options = _options(routes)
    existing = {
        question.route_id: question
        for question in db.query(ShuntingQuestion).filter_by(dataset_id=dataset.id).all()
    }
    inserted = updated = 0
    for route in routes:
        values = _question_values(route, options)
        question = existing.get(route.id)
        if question is None:
            db.add(ShuntingQuestion(dataset_id=dataset.id, route_id=route.id, **values))
            inserted += 1
            continue
        if any(getattr(question, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(question, key, value)
            updated += 1
    db.flush()
    return {"dataset_id": dataset.id, "inserted": inserted, "updated": updated, "total": len(routes)}


def public_question(question: ShuntingQuestion, route: ShuntingRoute) -> dict[str, Any]:
    fields = route.fields
    return {
        "id": question.id,
        "question_key": question.question_key,
        "route_number": route.route_number,
        "direction": fields["方向"],
        "route": fields["进路"],
        "title": question.title,
        "prompt": question.prompt,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "options": question.options,
        "is_active": question.is_active,
    }


def answer_key(question: ShuntingQuestion, route: ShuntingRoute) -> dict[str, Any]:
    result = public_question(question, route)
    result.update({
        "answer_spec": question.answer_spec,
        "source_fields": route.fields,
        "source_rich_text": route.rich_text,
        "source_provenance": route.provenance,
    })
    return result


def evaluate_answer(question: ShuntingQuestion, answer: dict[str, Any]) -> dict[str, Any]:
    expected = _answer_values(question.answer_spec)
    submitted_buttons = list(dict.fromkeys(str(value).strip() for value in answer.get("route_buttons", []) if str(value).strip()))
    submitted_switches = {
        str(code).strip(): str(position).strip()
        for code, position in (answer.get("switches") or {}).items()
        if str(code).strip() and str(position).strip()
    }
    submitted_switch_roles = {
        str(code).strip(): str(role).strip()
        for code, role in (answer.get("switch_roles") or {}).items()
        if str(code).strip() and str(role).strip()
    }
    submitted_hostile = list(dict.fromkeys(str(value).strip() for value in answer.get("hostile_signals", []) if str(value).strip()))
    submitted_sections = list(dict.fromkeys(str(value).strip() for value in answer.get("track_sections", []) if str(value).strip()))

    expected_buttons = set(expected["route_buttons"])
    expected_switches = expected["switches"]
    expected_switch_roles = expected.get("switch_roles", {})
    expected_hostile = set(expected["hostile_signals"])
    expected_sections = set(expected["track_sections"])
    submitted_button_set = set(submitted_buttons)
    submitted_hostile_set = set(submitted_hostile)
    submitted_section_set = set(submitted_sections)
    errors = {
        "route_buttons": {
            "missing": sorted(expected_buttons - submitted_button_set, key=_sort_key),
            "extra": sorted(submitted_button_set - expected_buttons, key=_sort_key),
        },
        "switches": {
            "missing": sorted(set(expected_switches) - set(submitted_switches), key=_sort_key),
            "extra": sorted(set(submitted_switches) - set(expected_switches), key=_sort_key),
            "wrong_position": [
                {"switch": code, "student": submitted_switches[code], "expected": expected_switches[code]}
                for code in sorted(set(expected_switches) & set(submitted_switches), key=_sort_key)
                if submitted_switches[code] != expected_switches[code]
            ],
            "missing_role": sorted(set(expected_switch_roles) - set(submitted_switch_roles), key=_sort_key),
            "extra_role": sorted(set(submitted_switch_roles) - set(expected_switch_roles), key=_sort_key),
            "wrong_role": [
                {"switch": code, "student": submitted_switch_roles[code], "expected": expected_switch_roles[code]}
                for code in sorted(set(expected_switch_roles) & set(submitted_switch_roles), key=_sort_key)
                if submitted_switch_roles[code] != expected_switch_roles[code]
            ],
        },
        "hostile_signals": {
            "missing": sorted(expected_hostile - submitted_hostile_set, key=_sort_key),
            "extra": sorted(submitted_hostile_set - expected_hostile, key=_sort_key),
        },
        "track_sections": {
            "missing": sorted(expected_sections - submitted_section_set, key=_sort_key),
            "extra": sorted(submitted_section_set - expected_sections, key=_sort_key),
        },
    }
    expected_total = len(expected_buttons) + len(expected_switches) + len(expected_hostile) + len(expected_sections)
    matched = (
        len(expected_buttons & submitted_button_set)
        + sum(1 for code, position in submitted_switches.items() if expected_switches.get(code) == position and submitted_switch_roles.get(code) == expected_switch_roles.get(code))
        + len(expected_hostile & submitted_hostile_set)
        + len(expected_sections & submitted_section_set)
    )
    all_correct = not any(
        group.get("missing") or group.get("extra") or group.get("wrong_position")
        for group in errors.values()
    )
    category_totals = {
        "route_buttons": (len(expected_buttons), len(expected_buttons & submitted_button_set)),
            "switches": (len(expected_switches), sum(1 for code, position in submitted_switches.items() if expected_switches.get(code) == position and submitted_switch_roles.get(code) == expected_switch_roles.get(code))),
        "hostile_signals": (len(expected_hostile), len(expected_hostile & submitted_hostile_set)),
        "track_sections": (len(expected_sections), len(expected_sections & submitted_section_set)),
    }
    return {
        "all_correct": all_correct,
        "score": round(matched / expected_total, 4) if expected_total else 1.0,
        "matched_items": matched,
        "expected_items": expected_total,
        "details": {
            "errors": errors,
            "category_scores": {
                name: {"matched": matched_count, "expected": total}
                for name, (total, matched_count) in category_totals.items()
            },
        },
        "feedback": "答案全部正确。" if all_correct else "答案已完成比对，请按错误类别调整后重新提交。",
    }
