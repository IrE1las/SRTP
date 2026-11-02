# 标准站共享运行与资料追溯（S1）

当前只保留原软件标准站引擎和共用运行能力。旧教学工作簿加载器、教学站专属数据、自由会话HTTP接口及独立页面已删除；标准站内嵌于理论专题1—4、教师答案录制/预览、学生操作学习和考试。理论观察不采集为学习或考试答卷；各正式作答使用独立会话及持久化日志。

| 来源或实现 | 当前用途 |
|---|---|
| reference_data.json | 原应用SDM、SWJDATA和STADATA解析值、来源标识及几何 |
| reference_station.py | 独立编译199条原应用进路，不读取理论教学表 |
| reference_runtime.py、reference_points.py、reference_sequence.py | 标准站条件、道岔反馈、进路状态及显示时序 |
| runtime.py | 注入站场包的共用会话、锁闭和计时原语；无默认教学站，无全局自由会话 |
| commands.py、console_commands.py | 共用命令及会话序列化；由理论观察、录制、操作学习及考试各自校验权限 |
| ReferenceStationDiagram.vue、standardDisplay.js | 保留的标准站绘图与显示；当前无独立路由 |
| tools/reference_simulator/、public/simulator-reference/ | 原软件解析/追溯工具及图片资源 |

理论六专题仍采用ai_design/station下的原图拓扑、核对联锁表及既有专业规则，与标准站运行资料分开。

既有道岔反馈、同位共用、取消及释放延时逻辑不因S1改动。专业重建与原软件证据边界见根目录《标准站软件复刻说明.md》。本次源码及状态机测试通过不代表运行原EXE的全部行为对照完成；本轮没有浏览器验收。


## S1返修的平台边界

TheorySimulationConsole.vue与api/theory_console.py为六专题中的1—4提供题内操作台，接口绑定规范题目键和当前用户，拒绝5/6专题及跨用户、跨题会话。模拟行车、故障和占用只影响本题观察状态，不写入LabAttempt。5—6仍由TheoryStationCanvas.vue显示原图联锁表资料。

2026-11-02按用户新增需求，学生“学习界面”增加与理论学习、操作学习平行的“仿真操作”（/student/learn/simulation）。同一组件以practice模式复用标准站图形及联锁引擎，通过/api/simulation-practice使用独立内存会话存储，绑定当前学生，不绑定题目，不写学习答卷、考试或成绩。全屏为自愿的显示切换，不套用考试限时、退出次数或交卷规则；刷新恢复本标签页当前会话，显式初始化或服务重启后重新开始。旧/api/simulation-console及/student/simulation-console等历史入口继续移除，不恢复旧练习/评分系统，也不更改标准站专业规则。
