"""Ordered server-event grading; browser claims never supply evidence."""


def lookup(snapshot, path):
    value = snapshot
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def matches(checkpoint, event, route_definitions):
    command, response = event["command"], event["response"]
    if command["type"] != checkpoint["type"] or response["reason_code"] != checkpoint["reason_code"]:
        return False
    if checkpoint["target"] != "@route" and command.get("target") != checkpoint["target"]:
        return False
    if any(command.get("payload", {}).get(k) not in (v if isinstance(v, list) else [v]) for k, v in checkpoint["payload"].items()):
        return False
    if checkpoint.get("route_id") and response.get("route_id") != checkpoint["route_id"]:
        return False
    if checkpoint.get("buttons") and response.get("button_sequence") != checkpoint["buttons"]:
        return False
    if checkpoint.get("device") and checkpoint["device"] not in response.get("devices", []):
        return False
    snapshot = response["snapshot"]
    if any(lookup(snapshot, k) != v for k, v in checkpoint["state"].items()):
        return False
    expectation = checkpoint.get("route_expect")
    if expectation:
        routes = [r for r in snapshot["routes"] if r["route_id"] == checkpoint["route_id"]]
        if expectation == "absent":
            if any(r["status"] not in {"cancelled", "released"} for r in routes):
                return False
        else:
            if not routes:
                return False
            r = routes[-1]
            if r["status"] != {"open": "signal_open"}.get(expectation, expectation):
                return False
            if expectation in {"open", "closed_locked"}:
                definition = route_definitions[r["route_id"]]
                if any(r["id"] not in snapshot["sections"][name]["owners"] for name in definition["sections"]):
                    return False
                if any(snapshot["switches"][sid]["position"] != pos or r["id"] not in snapshot["switches"][sid]["owners"] for sid, pos in definition["switches"].items()):
                    return False
    if response["reason_code"] != "OK":
        # A refusal may clear only the pending button sequence, never safety state.
        if any(event["before_snapshot"][k] != snapshot[k] for k in ("sections", "switches", "signals", "routes")):
            return False
    return True


def grade(question, events):
    cursor = 0
    results = []
    for number, checkpoint in enumerate(question["checkpoints"], 1):
        found = next((i for i in range(cursor, len(events)) if matches(checkpoint, events[i], question["route_definitions"])), None)
        passed = found is not None
        if passed:
            cursor = found + 1
        evidence = events[found] if passed else next((e for e in events[cursor:] if e["command"]["type"] == checkpoint["type"]), None)
        results.append({"number": number, "label": checkpoint["label"], "passed": passed,
                        "points": checkpoint["points"] if passed else 0, "possible": checkpoint["points"],
                        "event_id": evidence["response"]["event_id"] if evidence else None,
                        "student_operation": evidence["command"] if evidence else None,
                        "reason_code": evidence["response"]["reason_code"] if evidence else "MISSING_STEP",
                        "devices": evidence["response"].get("devices", []) if evidence else [checkpoint["target"]],
                        "message": "操作、顺序与实际状态符合要求。" if passed else "未找到按题设顺序完成的有效证据。" + (f" 最近相关操作：{evidence['response']['message']}。" if evidence else ""),
                        "correction": "" if passed else f"请从上一个已完成步骤继续，核对题设条件、目标设备和操作结果，再完成“{checkpoint['label']}”。"})
        # Do not award later actions performed before a missing prerequisite.
        if not passed:
            cursor = len(events)
    # Successful intermediate steps do not excuse damaging their final state.
    final_requirements = {}
    final_routes = {}
    for i, checkpoint in enumerate(question["checkpoints"]):
        for path, expected in checkpoint["state"].items():
            final_requirements[path] = (i, expected)
        if checkpoint.get("route_expect"):
            final_routes[checkpoint["route_id"]] = (i, checkpoint["route_expect"])
    if events:
        snapshot = events[-1]["response"]["snapshot"]
        failed = {i for path, (i, expected) in final_requirements.items() if lookup(snapshot, path) != expected}
        for rid, (i, expectation) in final_routes.items():
            routes = [r for r in snapshot["routes"] if r["route_id"] == rid]
            if expectation == "absent":
                mismatch = any(r["status"] not in {"released", "cancelled"} for r in routes)
            else:
                mismatch = not routes or routes[-1]["status"] != {"open": "signal_open"}.get(expectation, expectation)
            if mismatch:
                failed.add(i)
        for i in failed:
            if results[i]["passed"]:
                results[i].update(passed=False, points=0, message="曾完成该步骤，但提交时相关设备或进路状态已被后续操作改变。",
                                  correction="回放后续操作，核对题目要求的最终状态。", event_id=events[-1]["response"]["event_id"],
                                  devices=events[-1]["response"].get("devices", []))
    total = sum(r["possible"] for r in results)
    earned = sum(r["points"] for r in results)
    return {"question_id": question["id"], "earned": earned, "possible": total,
            "score": round(100 * earned / total, 1) if total else None,
            "checkpoints": results, "notes_scored": False, "scoring_version": question["scoring_version"]}
