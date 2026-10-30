# SRTP 铁路联锁学习与考试平台

S1—S6 功能已完成，当前为 S7 最终回归与交付（2026-10-30）。实际目录 `G:\gg\SRTP`，分支 `main`，基线 `ee6bfd8`；本轮修改尚未提交或推送，等待最终人工验收。

平台保留学校标识和蓝白界面，提供六专题理论学习、标准站操作题录制与学习、全屏限时考试，以及教师手工录分、保存草稿和发布成绩。考试没有自动评分、建议分或 AI 评价。最新三项反馈见[界面调整与验证](验收文档/S7_三项界面调整与验证.md)：用户角色筛选、已停用题目强制删除、成绩两按钮直接发布。

## 启动与本机数据库

需要 Python 3.12+ 和 Node.js/npm。已有依赖的机器继续双击 `启动项目.bat`，或运行：

```powershell
Set-Location G:\gg\SRTP
.\启动项目.ps1 -NoBrowser
```

自行打开 [平台首页](http://127.0.0.1:5173/)。停止使用 `.\停止项目.ps1`。启动器会准备依赖、首次生成本机 `.env` 和随机会话密钥；启动前检查结构，**不会静默迁移旧数据库**。

**2026-10-30 启动恢复：当前 G 盘 `framework/backend/railway.db` 已在备份和副本演练后显式升级 S6。**原 20 张表及 4 个账号、18 道理论题、2 份理论答卷、35 条调车资料、4 道操作题和 4 场考试保持；新增成绩三表为空，真实配置未改。原启动入口已通过预检并成功启动。现在可直接使用原入口，无需重复迁移，详见[本机启动恢复记录](验收文档/S7_启动恢复记录.md)。S7 首轮交付时“实际库仍 S5”是本次修复前的历史状态。

下列命令仅供其他尚未升级的 S5 库参考：确认没有进行中的考试后，停止服务，先预览、备份并在副本演练，再显式执行 S6。

```powershell
.\停止项目.ps1
.\.runtime\venv\Scripts\python.exe framework/backend/scripts/migrate_s6.py --database framework/backend/railway.db
# 确认预览与副本结果后显式应用；脚本会先自动备份：
.\.runtime\venv\Scripts\python.exe framework/backend/scripts/migrate_s6.py --database framework/backend/railway.db --apply
.\启动项目.ps1 -NoBrowser
```

S6 是本次最终数据库结构，S7 没有新增迁移脚本或启动模式；健康接口继续显示 `stage: S6`。全新安装直接初始化最终结构，创建 `admin / 00000000`；已有账号及其密码不重置。管理员可在首页修改自己的密码。

更早的库必须依次检查并执行 S1→S2→S3→S4→S5→S6；完整准备、逐阶段命令和失败恢复见[接管与使用说明](接管与使用说明.md)。不要删除现有数据库来解决升级问题，也不要将回归测试库替换为实际库。

## 三角色使用

| 角色 | 导航与主要流程 |
| --- | --- |
| 学生 | 首页；学习界面→理论学习/操作学习；考试界面→当前考试/历史考试 |
| 教师 | 首页；题目管理→理论学习批阅/操作学习出题与批阅；考试管理→考试详情→考试答卷→查看与批阅 |
| 管理员 | 首页、用户管理、AI设置；操作题与考试管理从首页内部链接进入 |

理论六专题和操作学习使用独立作答、反馈与批阅流程。理论专题 1—4 内嵌原软件标准站观察操作台，5—6 使用原图联锁表；操作学习与考试固定标准站。每页 6 条，空列表不生成虚构数据。

操作学习不限时、不强制全屏，业务点击完全一致为 100 分，否则“错误”、分数 `null`；AI 只作讲解，失败不影响提交。考试发布时保存名单、题目版本、标准答案和初始条件，每人一次机会；退出全屏、刷新及断线继续计时。人工成绩可保存私有草稿，也可输入完成后直接点击“发布成绩”，在弹窗核对当前分数和评语后一次完成发布；更正草稿发布前学生仍看旧版。

详细操作见[教师与管理员使用说明](管理员出题与批阅使用说明.md)、[六专题说明](实验专题题库说明.md)和[项目内容大纲](项目内容大纲.md)。

## 验证与最终验收

```powershell
# 测试在导入应用前隔离数据库和密钥，AI 使用替身。
.\.runtime\venv\Scripts\python.exe -m pytest framework/backend/tests --basetemp=.runtime/s7/manual-backend -q --tb=short
node --test framework/frontend/tests/*.test.mjs
npm --prefix framework/frontend run build
.\.runtime\venv\Scripts\python.exe framework/backend/scripts/check_s1_dependencies.py
.\.runtime\venv\Scripts\python.exe framework/backend/scripts/check_s7_delivery.py --output .runtime/s7/manual-audit.json
```

Windows 沙箱若阻止测试框架的本地 socketpair，会卡在 HTTP 测试准备阶段；这不是网页功能验证结果。本轮在允许本地通信的环境完成相同隔离测试，详见[代码验证记录](验收文档/S7_代码验证记录.md)。

最终交付：[S7操作验证流程](验收文档/S7_操作验证流程.txt)、[S7代码验证记录](验收文档/S7_代码验证记录.md)、[前端设计复核](验收文档/S7_前端设计复核.md)、[待办与未验证事项](验收文档/S7_待办与未验证事项.md)。S1—S6 验收文档作为阶段历史保留，旧路径、测试数量和数据库状态以当时机器为限。

## 配置与资料

网页 AI 配置在管理员“AI设置”和本机 `framework/backend/.env`，不使用 `ai/key.env`。`ai/`、`ai_design/ai/` 是独立资料脚本，不在网页启动链中；其中知识文档保留，本机密钥和生成缓存不纳入交付。S7 仅取消旧 `ai/key.env` 与 `ai/vector_db/` 的 Git 跟踪，磁盘原件保留；示例见 `ai/key.env.example`。

六专题题干、原图、标准答案、原始报告和标准站专业资料继续保留。旧三模块、经典例题、旧练习/统计、独立调车题库、7/8 专题及教学站切换不再提供运行入口。专业依据见 `ai_design/station/` 和[标准站软件复刻说明](标准站软件复刻说明.md)。代码回归通过不代表原 EXE 全部行为逐项对照完成。
