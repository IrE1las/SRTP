"""Experiment one, explicitly revised by the 2026-09-26 handoff design.

Never infer station-one answers from the older station-two report. The newer
handoff replaces its missing D1→D15 example with audited route 146.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from app.services.simulation_console.station import SOURCE_PATH, station_package

SOURCE_SHA = "fd32d5ed00723fc7ce146edc0cddf38d9062e54dcc60284b3bda92a4a352bf1d"
EXPORT_SHA = "f569b371fe3fcd8b10781d97ee49d67767e5fa99cb0e64697555672fb23b5043"
DESIGN_SHA = "7268f9e8fc408abf21068994f4e9920afe732c6c9961b8942c73f12d7c2d60c6"
DESIGN_REF = "联锁平台2.0_三模块前端与实验一1至5题_开发设计说明.doc"


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def action(kind, target, *, reason="OK", state=None, payload=None, label=None):
    return {"type": kind, "target": target, "reason_code": reason, "state": state or {},
            "payload": payload or {}, "label": label or f"{target}：{kind}", "points": 1}


def switch(kind, target="5/7", reason="OK", position=None):
    labels = {"SWITCH_TOTAL_NORMAL": "总定", "SWITCH_TOTAL_REVERSE": "总反", "SWITCH_SINGLE_LOCK": "单锁",
              "SWITCH_SINGLE_UNLOCK": "单解", "SWITCH_SEAL": "封闭", "SET_SWITCH_INDICATION": "失表示"}
    states = {}
    for sid in target.split("/"):
        if position is not None:
            states[f"switches.{sid}.position"] = position
        field = {"SWITCH_SINGLE_LOCK": ("manual_locked", True), "SWITCH_SINGLE_UNLOCK": ("manual_locked", False),
                 "SWITCH_SEAL": ("sealed", True), "SET_SWITCH_INDICATION": ("represented", False)}.get(kind)
        if field:
            states[f"switches.{sid}.{field[0]}"] = field[1]
    return action(kind, target, reason=reason, state=states, label=f"{target} 号道岔{labels.get(kind, kind)}")


def occupancy(target, kind="fault", state=None):
    return action("CLEAR_SECTION_OCCUPANCY" if kind == "clear" else "SET_SECTION_OCCUPANCY", target,
                  payload={} if kind == "clear" else {"kind": kind},
                  state={f"sections.{target}.occupancy_kind": kind, **(state or {})},
                  label=f"{target} {'恢复空闲' if kind == 'clear' else '车列占用' if kind == 'vehicle' else '故障占用'}")


def route(rid, reason="OK", device=None):
    definition = next(r for r in station_package()["routes"] if r["id"] == rid)
    return {**action("PRESS_BUTTON", definition["button_sequence"][-1], reason=reason,
                     state={f"signals.{definition['signal']}.aspect": definition["aspect"] if reason == "OK" else None},
                     label=f"办理 {definition['signal']} 进路并观察结果"),
            "route_id": rid, "buttons": definition["button_sequence"], "device": device,
            "route_expect": "open" if reason == "OK" else "absent"}


def repeat(rid, reason):
    definition = next(r for r in station_package()["routes"] if r["id"] == rid)
    return {**action("REPEAT_OPEN_SIGNAL", "@route", reason=reason,
                     state={f"signals.{definition['signal']}.aspect": definition["aspect"] if reason == "OK" else None},
                     label=f"{definition['signal']} 重复开放"), "route_id": rid, "route_expect": "open" if reason == "OK" else "closed_locked"}


def make_question(key, title, prompt, steps, *, position=None, env=None, status="active", future=None):
    q = {"id": key, "station_id": "station_1", "experiment_id": 1, "scenario_id": key,
         "title": title, "public_prompt": prompt, "question_version": "1.0", "scoring_version": "1.0",
         "report_ref": DESIGN_REF, "report_sha256": DESIGN_SHA, "export_sha256": EXPORT_SHA,
         "source_sha256": SOURCE_SHA, "status": status,
         "setup_mode": "student_action", "scenario": {"switch_positions": position or {}},
         "allowed_environment_commands": env or [], "checkpoints": steps, "future_capabilities": future or [],
         "source": {"document": DESIGN_REF, "section": title}, "notes_scored": False}
    referenced = {step["route_id"] for step in steps if step.get("route_id")}
    q["route_definitions"] = {r["id"]: {k: deepcopy(r[k]) for k in ("id", "sections", "switches", "signal", "aspect")}
                              for r in station_package()["routes"] if r["id"] in referenced}
    if status == "needs_teacher_review":
        originals = {
            "E1-5-5": "拟设 5DG 故障占用；按待设计的 X 引导办理命令尝试 X→IIIG，记录灯位并执行引导解锁。",
            "E1-5-6": "拟设 X 灯丝断丝，办理同一引导进路并解锁。",
            "E1-5-7": "先建 #7，拟设 5/7 失表示；尝试 X 引导、X 引导总锁闭及【总反/总定】→【27】，最后引导总解锁。",
        }
        q["original_text"] = originals[key]
        q["original_source"] = {"document": "设计相关/模块一_实验1.doc", "section": "六、实验内容逐题：5 接车与引导",
                                "sha256": "1d300d421944febbe52758c4eb538187908dcf86e3690dd23f9d0e379550353d"}
    q["fingerprint"] = fingerprint(q)
    return q


def environment(target, kinds, *, after_route=None):
    return {"target": target, "kinds": kinds, "after_route": after_route}


def build_questions():
    qs = []
    def add(*args, **kwargs):
        qs.append(make_question(*args, **kwargs))
    add("E1-1-1", "1（1）5/7 总反与总定", "在空闲场景对 5/7 依次总反、总定，观察两成员位置与表示。", [switch("SWITCH_TOTAL_REVERSE", position=1), switch("SWITCH_TOTAL_NORMAL", position=0)])
    for pos, name in [(0, "定位"), (1, "反位")]:
        add(f"E1-1-2-{pos}", f"1（2）9/11 {name}单锁与单解", f"9/11 初始{name}。单锁后依次尝试总定、总反；单解后再次总反、总定，观察整组位置。",
            [switch("SWITCH_SINGLE_LOCK", "9/11", position=pos), switch("SWITCH_TOTAL_NORMAL", "9/11", "SWITCH_MANUAL_LOCKED", pos),
             switch("SWITCH_TOTAL_REVERSE", "9/11", "SWITCH_MANUAL_LOCKED", pos), switch("SWITCH_SINGLE_UNLOCK", "9/11"),
             switch("SWITCH_TOTAL_REVERSE", "9/11", position=1), switch("SWITCH_TOTAL_NORMAL", "9/11", position=0)], position={"9": pos, "11": pos})
    add("E1-1-3", "1（3）7DG 占用时操岔", "设置 7DG 车列占用，再对 5/7 依次总反、总定，观察两成员是否转换。",
        [occupancy("7DG", "vehicle"), switch("SWITCH_TOTAL_REVERSE", reason="SECTION_OCCUPIED", position=0), switch("SWITCH_TOTAL_NORMAL", reason="SECTION_OCCUPIED", position=0)], env=[environment("7DG", ["vehicle", "clear"])])
    add("E1-1-4", "1（4）封闭与单独操纵", "封闭 5/7 后依次总反、总定，再尝试 D3 至 D13 调车进路，对比两类操作的结果。",
        [switch("SWITCH_SEAL"), switch("SWITCH_TOTAL_REVERSE", position=1), switch("SWITCH_TOTAL_NORMAL", position=0), route("146", "SEALED_FOR_ROUTE", "5")])
    add("E1-2A", "2A（1—3）组合长调车、锁闭与取消", "办理 D3 至 D13 组合长调车；尝试将 5/7 总反，再申请 SIII 至 D9 调车进路；未接近、未行车时总取消原进路。",
        [route("146"), switch("SWITCH_TOTAL_REVERSE", reason="SWITCH_ROUTE_LOCKED", position=0), route("101", "SECTION_LOCKED", "9-15DG"),
         {**action("CANCEL_ROUTE", "@route", label="总取消原进路", state={"signals.D3.aspect": None}), "route_id": "146", "route_expect": "cancelled"}])
    for pos, name in [(0, "定位"), (1, "反位")]:
        add(f"E1-2B-1-{pos}", f"2B（1）5/7 {name}单锁", f"将 5/7 操纵至{name}并单锁，然后办理 D3 至 D13 组合长调车，观察结果。",
            [switch("SWITCH_TOTAL_NORMAL" if pos == 0 else "SWITCH_TOTAL_REVERSE", position=pos), switch("SWITCH_SINGLE_LOCK", position=pos), route("146", "OK" if pos == 0 else "SWITCH_MANUAL_LOCKED")])
        add(f"E1-2B-2-{pos}", f"2B（2）5/7 {name}封闭", f"将 5/7 操纵至{name}并封闭，然后办理 D3 至 D13 组合长调车，观察结果。",
            [switch("SWITCH_TOTAL_NORMAL" if pos == 0 else "SWITCH_TOTAL_REVERSE", position=pos), switch("SWITCH_SEAL", position=pos), route("146", "SEALED_FOR_ROUTE")])
    add("E1-2B-3", "2B（3）5DG 故障占用", "设置 5DG 故障占用，再办理 D3 至 D13 组合长调车。", [occupancy("5DG"), route("146", "SECTION_OCCUPIED", "5DG")], env=[environment("5DG", ["fault", "clear"])])
    add("E1-2B-4", "2B（4）5/7 失表示", "设置 5/7 失去表示，再办理 D3 至 D13 组合长调车。", [switch("SET_SWITCH_INDICATION"), route("146", "SWITCH_UNREPRESENTED")], env=[environment("5/7", ["indication", "restore_indication"])])
    occupation = occupancy("9-15DG", "vehicle")
    occupation["payload"] = {"kind": ["vehicle", "fault"]}
    occupation["state"] = {"sections.9-15DG.occupied": True}
    add("E1-2B-5", "2B（5）9-15DG 占用", "设置 9-15DG 车列或故障占用并记录类型，再办理 D3 至 D13 组合长调车。", [occupation, route("146", "SECTION_OCCUPIED", "9-15DG")], env=[environment("9-15DG", ["vehicle", "fault", "clear"])])
    for key, title, rid, section, signal in [("E1-2C", "2C（1—2）故障与重复开放", "146", "5DG", "D3"), ("E1-3-3", "3（3）长调车故障与重复开放", "116", "19-27DG", "D1")]:
        dest = "D3 至 D13" if rid == "146" else "D1 至 4G"
        add(key, title, f"办理 {dest} 长调车；设置 {section} 故障，观察信号并尝试重复开放；恢复空闲，观察信号，再显式重复开放。全程不模拟行车。",
            [route(rid), occupancy(section, state={f"signals.{signal}.aspect": None}), repeat(rid, "SECTION_OCCUPIED"),
             occupancy(section, "clear", {f"signals.{signal}.aspect": None}), repeat(rid, "OK")], env=[environment(section, ["fault", "clear"], after_route=rid)])
    add("E1-3-1", "3（1）D1 至 4G 长调车", "确认 1/19WG 空闲，办理 D1 至 4G 长调车，观察全进路锁闭及信号。", [route("116")])
    add("E1-3-2", "3（2）长调车途经占用区段", "设置 1/19WG 车列占用，随后办理 D1 至 4G 长调车，观察拒绝原因。", [occupancy("1/19WG", "vehicle"), route("116", "SECTION_OCCUPIED", "1/19WG")], env=[environment("1/19WG", ["vehicle", "clear"])])
    add("E1-4-1", "4（1）S4 至 D1 分段长调车", "先办理 S4 至 D15 调车，再办理 D5 至 D1 调车，观察两段的独立锁闭和信号。", [route("96"), route("58")])
    add("E1-4-2", "4（2）SIII 至 XF 变通列车", "区间许可已满足，通过 BA 办理 SIII 至 XF 变通列车进路，观察信号及锁闭。", [route("182")])
    add("E1-4-3", "4（3）X 经 5/7 定位接至 IIIG", "5/7 初始定位，通过 BA 办理 X 至 IIIG 变通接车进路，观察道岔和区段锁闭。", [route("187")])
    for n, section, kind in [(1, "IIIG", "vehicle"), (2, "3DG", "fault")]:
        add(f"E1-5-{n}", f"5（{n}）{section} 占用时接车", f"设置 {section} {'车列' if kind == 'vehicle' else '故障'}占用，再办理 X 至 IIIG 正常接车进路。", [occupancy(section, kind), route("7", "SECTION_OCCUPIED", section)], env=[environment(section, [kind, "clear"])])
    add("E1-5-3", "5（3）相向接车进路", "先办理 S 至 IIIG 接车进路，再办理 X 至 IIIG，观察结果。可记录原因，文字本期不计分。", [route("38"), route("7", "SECTION_LOCKED", "IIIG")])
    add("E1-5-4", "5（4）接车与敌对调车", "先办理 S 至 IIIG 接车进路，再办理 D12 至 IIIG 调车进路，观察结果。可记录原因，文字本期不计分。", [route("38"), route("89", "HOSTILE_ROUTE")])
    for n, text, future in [(5, "设置 5DG 故障，尝试 X 至 IIIG 引导并执行引导解锁。", ["guiding_route", "guiding_unlock"]),
                             (6, "设置 X 灯丝断丝，办理同一引导进路并解锁。灯丝类别待教师确认。", ["filament_fault", "guiding_route"]),
                             (7, "建立正常接车后设置 5/7 失表示，尝试 X 引导、引导总锁闭与 27 总反/总定，最后引导总解锁。", ["guiding_global_lock", "guiding_unlock"])]:
        add(f"E1-5-{n}", f"5（{n}）待教师确认", text, [], status="needs_teacher_review", future=future)
    return qs


QUESTIONS = {q["id"]: q for q in sorted(build_questions(), key=lambda q: q["id"])}


def validate_source():
    package = station_package()
    if package["source_sha256"].lower() != SOURCE_SHA:
        raise ValueError("一号车站源数据版本变化，题目需重新核验")
    root = Path(__file__).resolve().parents[5]
    workbook = root / "设计相关/data.xls"
    if not workbook.is_file() or sha256(workbook.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError("data.xls 来源指纹不符，题目停用待核验")
    if sha256(SOURCE_PATH.read_bytes()).hexdigest() != EXPORT_SHA:
        raise ValueError("站场导出数据已变化，题目停用待核验")
    routes = {r["id"]: r for r in package["routes"]}
    for q in QUESTIONS.values():
        for c in q["checkpoints"]:
            if c.get("route_id") and routes[c["route_id"]]["status"] != "ready":
                raise ValueError(f"{q['id']} 引用了不可办理的进路")
            if c.get("buttons") and routes[c["route_id"]]["button_sequence"] != c["buttons"]:
                raise ValueError("题目按钮与当前数据不符")
    return sha256(SOURCE_PATH.read_bytes()).hexdigest()


def public_question(q):
    keys = ("id", "station_id", "experiment_id", "scenario_id", "title", "public_prompt", "status", "question_version", "setup_mode", "scenario", "allowed_environment_commands", "notes_scored", "future_capabilities")
    return {k: deepcopy(q[k]) for k in keys}
