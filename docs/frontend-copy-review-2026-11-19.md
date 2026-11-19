# 前端文案筛选清单

本清单只收集候选文案，本轮未批量删除。可按编号回复保留、删除或改写，例如“删除 T001、T005，保留 T010”。题干中的实际条件和操作步骤单独标注，便于逐项筛选。

实验01、02新增的题目未添加宣传副标题。下表包括现有题目、登录页、公共横幅、录题和作答页面中的候选文字。

共 63 项。

| 编号 | 类别 | 原文 | 建议 | 位置 |
|---|---|---|---|---|
| T001 | 实验专题副标题 | 比较单操、锁闭、占用与封闭，解释进路能否建立。 | 可删除副标题；保留章节名称。 | [ai_design/station/report_topic_blueprint.json:35](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:35) |
| T002 | 实验专题副标题 | 区分取消进路、人工解锁与区段故障解锁，记录解锁时序。 | 可删除副标题；保留章节名称。 | [ai_design/station/report_topic_blueprint.json:42](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:42) |
| T003 | 实验专题副标题 | 按占用和出清顺序分析信号关闭与分段解锁。 | 可删除副标题；保留章节名称。 | [ai_design/station/report_topic_blueprint.json:49](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:49) |
| T004 | 实验专题副标题 | 对比故障位置、出现时机和故障类型，解释安全后果。 | 可删除副标题；保留章节名称。 | [ai_design/station/report_topic_blueprint.json:56](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:56) |
| T005 | 实验专题副标题 | 读懂原图设备关系，填写列车进路联锁表并解释带动道岔。 | 可删除副标题；保留章节名称。 | [ai_design/station/report_topic_blueprint.json:63](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:63) |
| T006 | 实验专题副标题 | 填写调车联锁表，辨认防护、带动与条件敌对。 | 可删除副标题；保留章节名称。 | [ai_design/station/report_topic_blueprint.json:70](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:70) |
| T007 | 题目前置说明 | 以标准站5/7、9/11号道岔为对象。每一行均为独立工况，除列明条件外，道岔有表示、区段空闲且未被进路锁闭。分别判断能否转换，并解释“封闭”和“单锁”的区别。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:82](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:82) |
| T008 | 题目前置说明 | 办理标准站D1至D5的短调车进路。填写始终端按钮、道岔位置和走行区段，再比较同时办理SII至D1长调车进路时受什么限制。本题核对依据为标准站进路定义，不套用原图联锁表的进路编号。按钮填写操作台名称，例如D1DA。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:160](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:160) |
| T009 | 题目前置说明 | 拟将车列由标准站D1调入4股道，分别研究1/19WG空闲、由车辆或故障占用两种条件下的一次办理与分段办理。标准站一次办理按D1、S4调车按钮；分段办理先办D15至S4，再办D1至D15。逐次记录能否选路、信号及锁闭情况，不将原报告的观测结果直接当作本软件的实测结果。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:229](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:229) |
| T010 | 题目前置说明 | 针对标准站D3至D11调车进路，比较IAG空闲和有车停留两种情况。已知本题进路内各检查区段空闲。记录关闭信号、请求解锁与实际解锁的先后关系。不得把“信号关闭”直接当作“进路已解锁”。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:285](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:285) |
| T011 | 题目前置说明 | 以标准站XD至III股道、XD至5股道接车为对象，分别比较接近区段有车和无车时的取消与人工解锁。接近区段按标准站进路面板所列信息设置，记录区段名称、信号关闭、锁闭保持和实际解锁时间。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:335](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:335) |
| T012 | 题目前置说明 | 办理标准站SIII至D3的牵出进路，比较车列仅占9DG、15DG、以及继续运行后同时占9DG、15DG和3DG两种工况，再由D13向II股道折返。记录头尾位置、折返信号和未走完的牵出进路，区分实际运行观察与推测。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:377](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:377) |
| T013 | 题目前置说明 | 按标准站D3至D7的短调车进路，车列沿5DG进入3DG。本题只排序车列正向运行时的观测事件；不据此直接判定继电解锁完成。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:431](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:431) |
| T014 | 题目前置说明 | 围绕标准站D3方向调车，比较IAG一直留车与随车列前行出清；再比较D3至D11建立后立即设置3DG故障占用，以及车列已依次占用IAG、5DG后再设置同一故障。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:483](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:483) |
| T015 | 题目前置说明 | 选择标准站从X进入I股道的接车走行路径，按IAG、5DG、3DG、9DG、15DG、17DG、23DG、IG依次模拟占用。比较3DG持续故障占用，以及车列通过后道岔失去表示两类工况。网页用于提交实验记录，不驱动真实设备。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:538](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:538) |
| T016 | 题目前置说明 | 标准站D1至D5进路已锁闭，道岔1/3定位且有表示。有人认为“道岔有表示、1DG也空闲，所以现在总反一定成功”。判断这一结论并给出纠正理由。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:595](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:595) |
| T017 | 题目前置说明 | 以X向I股道接车路径上的3DG为观察区段。设计“无车却出现占用”“有车却短暂显示空闲”“有车但持续显示空闲”三组工况，沿同一车列运行次序比较。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:638](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:638) |
| T018 | 题目前置说明 | 针对标准站X向I股道接车，比较列车前方1/3失去表示与列车所在区段5/7失去表示，再分析引导进路已办理时5/7失去表示的情况。提出需要确认的条件和处理思路。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:692](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:692) |
| T019 | 题目前置说明 | 将实验5的列车进路联锁表填写方法迁移到原图。办理东郊方面经XD至III股道接车，填写下列栏目；其余原表栏目可在补充说明中记录。用逗号或顿号分隔设备，保留括号。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:747](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:747) |
| T020 | 题目前置说明 | 按原图办理东郊方面经XD至4股道接车。填写关键联锁栏目并说明哪些道岔实际走行，哪些用于防护或带动。大括号与方括号不能互换。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:837](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:837) |
| T021 | 题目前置说明 | 报告原题使用草海站完整上下行咽喉；本题仅依据当前原图圈定范围作答。先识别区段，再说明若要编写完整通过进路联锁表还需要哪些资料。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:918](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:918) |
| T022 | 题目前置说明 | 按核对表27号，在原图办理D9至5股道调车。按实验6表格形式填写信号、道岔和区段，说明交叉渡线的防护关系。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:986](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:986) |
| T023 | 题目前置说明 | 按核对表34号，在原图办理D13至II股道调车。重点判断23/25的作用及27号道岔的位置，填写下列栏目。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:1089](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:1089) |
| T024 | 题目前置说明 | 按核对表20号研究D1至D9。原图5/7在本题假定处于定位。填写道岔与区段，再解释条件敌对的写法；条件前缀与后续信号的适用关系需整体阅读，不能逐个逗号盲目拆开。 | 可精简重复说明；涉及工况、步骤或提问的部分需单独筛选。 | [ai_design/station/report_topic_blueprint.json:1171](D:/srtp/SRTP/ai_design/station/report_topic_blueprint.json:1171) |
| T025 | 页面说明或副标题 | 本记录未采集逐步操作，可在“错误与教学反馈”查看已保存的提交结果。 | 可删除或缩短；请筛选。 | [framework/frontend/src/features/learningRecords/LearningRecords.vue:23](D:/srtp/SRTP/framework/frontend/src/features/learningRecords/LearningRecords.vue:23) |
| T026 | 页面说明或副标题 | 本记录尚无教学解析或教师评语。 | 可删除或缩短；请筛选。 | [framework/frontend/src/features/learningRecords/LearningRecords.vue:29](D:/srtp/SRTP/framework/frontend/src/features/learningRecords/LearningRecords.vue:29) |
| T027 | 文件来源或实现说明 | 明确选择目标，不能从题干推测 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/features/operationQuestions/AssessmentConfig.vue:9](D:/srtp/SRTP/framework/frontend/src/features/operationQuestions/AssessmentConfig.vue:9) |
| T028 | 页面说明或副标题 | 当前版本只读。需要调整时，请先修改题设建立新草稿，再配置评价。 | 可删除或缩短；请筛选。 | [framework/frontend/src/features/operationQuestions/AssessmentConfig.vue:17](D:/srtp/SRTP/framework/frontend/src/features/operationQuestions/AssessmentConfig.vue:17) |
| T029 | 页面说明或副标题 | 列车：先点绿色列车按钮，再点终端列车按钮。调车：依次点击始端、终端信号灯。 | 建议保留；属于操作方法，可按需缩短。 | [framework/frontend/src/features/simulationConsole/SimulationConsole.vue:29](D:/srtp/SRTP/framework/frontend/src/features/simulationConsole/SimulationConsole.vue:29) |
| T030 | 页面说明或副标题 | 操纵道岔：先按“总定位 / 总反位 / 单锁 / 单解”，再点道岔编号；双动道岔整组执行。 | 建议保留；属于操作方法，可按需缩短。 | [framework/frontend/src/features/simulationConsole/SimulationConsole.vue:30](D:/srtp/SRTP/framework/frontend/src/features/simulationConsole/SimulationConsole.vue:30) |
| T031 | 页面说明或副标题 | 总取消、总人解和重开信号：先按功能按钮，再点原进路的始端信号。功能按钮 15 秒未选择目标自动复原。 | 建议保留；属于操作方法，可按需缩短。 | [framework/frontend/src/features/simulationConsole/SimulationConsole.vue:31](D:/srtp/SRTP/framework/frontend/src/features/simulationConsole/SimulationConsole.vue:31) |
| T032 | 页面说明或副标题 | 移动端先按“设备菜单”，再点道岔、信号机、股道或闭塞框，即可打开同样的菜单；每次选中后自动退出，按 Esc 或再次按按钮可取消。双动道岔整组设置和恢复表示，任一端在进路内时禁止设置整组失表示。灯丝断丝时引导仍可办理，但信号不能点亮。 | 建议保留；属于操作方法，可按需缩短。 | [framework/frontend/src/features/simulationConsole/SimulationConsole.vue:38](D:/srtp/SRTP/framework/frontend/src/features/simulationConsole/SimulationConsole.vue:38) |
| T033 | 页面说明或副标题 | 学生可在站场自由操作；完整进路条件和核对清单由教师查看。 | 可删除或缩短；请筛选。 | [framework/frontend/src/features/simulationConsole/SimulationConsole.vue:60](D:/srtp/SRTP/framework/frontend/src/features/simulationConsole/SimulationConsole.vue:60) |
| T034 | 文件来源或实现说明 | 搜索资料名称、文件名或说明 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/admin/KnowledgeLibrary.vue:20](D:/srtp/SRTP/framework/frontend/src/views/admin/KnowledgeLibrary.vue:20) |
| T035 | 文件来源或实现说明 | 资料库加载失败，请重试。 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/admin/KnowledgeLibrary.vue:40](D:/srtp/SRTP/framework/frontend/src/views/admin/KnowledgeLibrary.vue:40) |
| T036 | 页面说明或副标题 | 课件、教材摘录和教师整理的文字说明都可以作为 AI 解释的依据。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/admin/KnowledgeLibrary.vue:49](D:/srtp/SRTP/framework/frontend/src/views/admin/KnowledgeLibrary.vue:49) |
| T037 | 页面说明或副标题 | 例如：杨扬《车站信号自动控制》课件，用于解释进路、信号及联锁电路。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/admin/KnowledgeLibrary.vue:132](D:/srtp/SRTP/framework/frontend/src/views/admin/KnowledgeLibrary.vue:132) |
| T038 | 文件来源或实现说明 | 填写对应实验报告位置，或自编题所依据的资料。 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/admin/QuestionEditor.vue:13](D:/srtp/SRTP/framework/frontend/src/views/admin/QuestionEditor.vue:13) |
| T039 | 文件来源或实现说明 | field.kind==='essay'?'填写有资料支持的参考解答，注明仍需实测或资料核实的部分。':'解释为什么这样填写；说明常见错误及纠正方法。' | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/admin/QuestionEditor.vue:32](D:/srtp/SRTP/framework/frontend/src/views/admin/QuestionEditor.vue:32) |
| T040 | 页面说明或副标题 | 理解错误，是掌握知识的开始 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/auth/Login.vue:29](D:/srtp/SRTP/framework/frontend/src/views/auth/Login.vue:29) |
| T041 | 页面说明或副标题 | 选择专题，在站场中观察，再完成题目作答。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/student/LabTopics.vue:3](D:/srtp/SRTP/framework/frontend/src/views/student/LabTopics.vue:3) |
| T042 | 文件来源或实现说明 | 按工况逐项记录：条件 → 现象 → 原因。区分实测与推测，并写出依据。 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/student/LabTopics.vue:25](D:/srtp/SRTP/framework/frontend/src/views/student/LabTopics.vue:25) |
| T043 | 文件来源或实现说明 | 实验专题以本项目原始报告为依据；管理员新增或修订题目按本题标注的命题依据与评分规则评阅，专题1—4使用标准站操作台，专题5—6使用原始图站场。 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/student/LabTopics.vue:31](D:/srtp/SRTP/framework/frontend/src/views/student/LabTopics.vue:31) |
| T044 | 文件来源或实现说明 | 填写教材位置、实验资料，或注明教师自编 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/teacher/ChapterQuestions.vue:21](D:/srtp/SRTP/framework/frontend/src/views/teacher/ChapterQuestions.vue:21) |
| T045 | 页面说明或副标题 | 发布后，本场考试使用发布时的学生名单、题目和初始条件；之后改班或改题不会影响本场考试。每名学生只有一次正式机会。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/ExamEditor.vue:28](D:/srtp/SRTP/framework/frontend/src/views/teacher/ExamEditor.vue:28) |
| T046 | 页面说明或副标题 | 先明确任务和初始条件，再进入站场录制标准答案。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationEditor.vue:3](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationEditor.vue:3) |
| T047 | 页面说明或副标题 | 请先结束当前录制或预览，再修改题设。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationEditor.vue:7](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationEditor.vue:7) |
| T048 | 文件来源或实现说明 | 班级来自现有学生资料，可多选。发布后仅所选班级可见。 | 可隐藏来源说明，来源信息保留在管理端。 | [framework/frontend/src/views/teacher/OperationEditor.vue:14](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationEditor.vue:14) |
| T049 | 页面说明或副标题 | 未选中的区段保持空闲。修改初始条件后，需要重新录制标准答案。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationEditor.vue:18](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationEditor.vue:18) |
| T050 | 页面说明或副标题 | 1. 写明任务，设置班级和初始条件。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationEditor.vue:24](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationEditor.vue:24) |
| T051 | 页面说明或副标题 | 2. 在站场完成一遍标准操作，结束录制并保存答案。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationEditor.vue:24](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationEditor.vue:24) |
| T052 | 页面说明或副标题 | 题目暂未写完时，可以先保存草稿，稍后继续。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationEditor.vue:24](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationEditor.vue:24) |
| T053 | 页面说明或副标题 | 核对学生会看到的题面、初始条件和标准操作，再发布。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationReview.vue:3](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationReview.vue:3) |
| T054 | 页面说明或副标题 | 进入站场完成标准操作，结束录制并保存答案后，日志会显示在这里。 | 可删除或缩短；请筛选。 | [framework/frontend/src/views/teacher/OperationReview.vue:11](D:/srtp/SRTP/framework/frontend/src/views/teacher/OperationReview.vue:11) |
| T055 | 口号 | 从一条进路开始，理解每一次操作背后的联锁逻辑。 | 建议删除。 | [framework/frontend/src/components/CampusBanner.vue:21](D:/srtp/SRTP/framework/frontend/src/components/CampusBanner.vue:21) |
| T056 | 口号 | 关注学习过程，让每一次反馈都成为成长的起点。 | 建议删除。 | [framework/frontend/src/components/CampusBanner.vue:21](D:/srtp/SRTP/framework/frontend/src/components/CampusBanner.vue:21) |
| T057 | 口号 | 铁路联锁实训 · 从自主作答到错误定位，让每一次练习都有收获。 | 建议删除。 | [framework/frontend/src/components/CampusBanner.vue:21](D:/srtp/SRTP/framework/frontend/src/components/CampusBanner.vue:21) |
| T058 | 文件来源或实现说明 | 实验报告对应位置 | 建议隐藏整块来源展示。 | [framework/frontend/src/views/student/LabTopics.vue:31](D:/srtp/SRTP/framework/frontend/src/views/student/LabTopics.vue:31) |
| T059 | 文件来源或实现说明 | 学号+姓名+实验一、二.doc · 实验1 · 三、1（1）—（4） | 此项为动态展示示例；可隐藏文件名及来源位置。 | [framework/frontend/src/views/student/LabTopics.vue:31](D:/srtp/SRTP/framework/frontend/src/views/student/LabTopics.vue:31) |
| T060 | 结果页标题或占位内容 | ai分析日志 | 建议改为“操作核对结果”；此处是固定规则比对。 | [framework/frontend/src/features/operationQuestions/LearningResult.vue:4](D:/srtp/SRTP/framework/frontend/src/features/operationQuestions/LearningResult.vue:4) |
| T061 | 结果页标题或占位内容 | ai评价讲解 | 可改为“操作讲解”，或保留 AI 功能标识。 | [framework/frontend/src/features/operationQuestions/LearningResult.vue:12](D:/srtp/SRTP/framework/frontend/src/features/operationQuestions/LearningResult.vue:12) |
| T062 | 结果页标题或占位内容 | 分数：null | 建议改为“未评分”，保留评分状态。 | [framework/frontend/src/features/operationQuestions/LearningResult.vue:6](D:/srtp/SRTP/framework/frontend/src/features/operationQuestions/LearningResult.vue:6) |
| T063 | 结果页标题或占位内容 | null（讲解或教师评语为空时） | 建议显示“尚无讲解/评语”，避免暴露空值。 | [framework/frontend/src/features/operationQuestions/LearningResult.vue:13](D:/srtp/SRTP/framework/frontend/src/features/operationQuestions/LearningResult.vue:13) |
