"""Build a per-route evidence report from the imported station package.

Run from ``framework/backend`` with ``python -m app.services.simulation_console.audit``.
The result is deterministic apart from the workbook hash and route source rows.
"""

import csv
from pathlib import Path

from . import runtime


def build_audit(output_path: Path | None = None) -> dict[str, int]:
    output_path = output_path or Path(__file__).with_name("route_audit.csv")
    clock = [1000.0]
    original_monotonic = runtime.monotonic
    runtime.monotonic = lambda: clock[0]
    service = runtime.SimulationService()
    results = []
    try:
        for route in service.package["routes"]:
            status = "通过" if route["status"] == "ready" else "数据阻塞" if route["status"] == "blocked" else "阶段一排除"
            reason = "；".join(route["reasons"])
            evidence = ""
            if route["status"] == "ready":
                session = service.new_session(9000)
                response = None
                for button in route["button_sequence"]:
                    response = service.select_button(session["session_id"], 9000, button, session["version"])
                    session = response["snapshot"]
                if not response or not response["accepted"]:
                    status, reason = "运行失败", response["message"] if response else "无按钮动作"
                else:
                    instance = session["routes"][0]
                    if session["signals"][route["signal"]]["aspect"] != route["aspect"]:
                        status, reason = "运行失败", "开放灯位与联锁表不一致"
                    else:
                        steps = len(route["sections"]) + 1 + int(instance["progress"] == -2)
                        for _ in range(steps):
                            response = service.step_train(session["session_id"], 9000, instance["id"], session["version"])
                            session = response["snapshot"]
                            if not response["accepted"]:
                                status, reason = "运行失败", response["message"]
                                break
                        if status == "通过":
                            clock[0] += 3.1
                            session = service.snapshot(session["session_id"], 9000)
                            if session["routes"][0]["status"] != "released":
                                status, reason = "运行失败", "正常解锁后仍有未释放资源"
                            else:
                                evidence = "完整按钮序列；灯位；仿真接近/占用/出清；延时正常解锁"
            results.append({
                "进路编号": route["id"], "属性代码": route["attribute"],
                "工作表": route["source_sheet"], "原表行号": route["source_row"],
                "原按钮序列": route["source_button_sequence"], "防护信号": route["signal"],
                "开放代码": route["aspect"], "子进路": ",".join(route["subroutes"]),
                "验证状态": status, "原因": reason, "运行证据": evidence,
                "数据源SHA256": service.package["source_sha256"],
            })
    finally:
        runtime.monotonic = original_monotonic
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    counts = {status: sum(row["验证状态"] == status for row in results) for status in {row["验证状态"] for row in results}}
    return counts


if __name__ == "__main__":
    print(build_audit())
