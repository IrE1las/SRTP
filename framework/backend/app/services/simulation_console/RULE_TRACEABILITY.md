# 标准站共享运行与资料追溯（S1）

当前只保留原软件标准站引擎和共用运行能力。旧教学工作簿加载器、教学站专属数据、自由会话HTTP接口及独立页面已删除；2026-10-27返修将标准站内嵌到理论专题1—4；新的操作题录制与正式答题流程仍留S3/S4。

| 来源或实现 | 当前用途 |
|---|---|
| reference_data.json | 原应用SDM、SWJDATA和STADATA解析值、来源标识及几何 |
| reference_station.py | 独立编译199条原应用进路，不读取理论教学表 |
| reference_runtime.py、reference_points.py、reference_sequence.py | 标准站条件、道岔反馈、进路状态及显示时序 |
| runtime.py | 注入站场包的共用会话、锁闭和计时原语；无默认教学站，无全局自由会话 |
| commands.py、console_commands.py | 共用命令及会话序列化；后续由新业务接入权限边界 |
| ReferenceStationDiagram.vue、standardDisplay.js | 保留的标准站绘图与显示；当前无独立路由 |
| tools/reference_simulator/、public/simulator-reference/ | 原软件解析/追溯工具及图片资源 |

理论六专题仍采用ai_design/station下的原图拓扑、核对联锁表及既有专业规则，与标准站运行资料分开。

既有道岔反馈、同位共用、取消及释放延时逻辑不因S1改动。专业重建与原软件证据边界见根目录《标准站软件复刻说明.md》。本次源码及状态机测试通过不代表运行原EXE的全部行为对照完成；本轮没有浏览器验收。


## S1返修的平台边界

TheorySimulationConsole.vue与api/theory_console.py仅服务六专题中的1—4，接口绑定规范题目键和当前用户，拒绝5/6专题及跨用户、跨题会话。模拟行车、故障和占用只影响本题观察状态，不写入LabAttempt。5—6仍由TheoryStationCanvas.vue显示原图联锁表资料。旧独立自由仿真路由/API不恢复。
