# SRTP 铁路联锁实训

Vue 3 前端与 FastAPI 后端组成的铁路联锁教学网站，包含客观题库、六个实验专题、标准站仿真、教师操作录题、正式考试和账号管理。

## 项目资料

- `framework/frontend`：网页与站场图形交互。
- `framework/backend`：登录、题目、判分与AI解析接口。
- `ai_design/station`：专业规则、站场拓扑、核对后的联锁表和题目依据。
- `pictures`：站场原图等项目图片。
- `车站与区间控制实验`中的原始报告：当前六个专题校验其对应来源文件的哈希，不能单独修改原件后继续沿用旧题目。其余原件作为用户资料保留。

专业解释以本项目已有规则文件为最高约束。详细操作见根目录的各项功能说明。

2026-11-15：成员版题库与界面已补充正式考试、教师操作录题、操作学习和完整账号管理；学生自由仿真支持行车、占用和故障设置。入口、权限及已有数据库升级说明见 [录题、考试与账号管理](docs/teaching-workflows-2026-11-15.md)。

## 首次运行

需要Python 3.12+及Node.js/npm（Windows）。

双击根目录`启动项目.bat`（或运行`启动项目.ps1`）即可，启动器会自动完成本机首次准备，之后每次启动也会自动检查：

1. 创建`.runtime/venv`虚拟环境，并按`framework/backend/requirements.lock.txt`安装后端依赖（锁文件更新时自动重装）；
2. 缺少`framework/backend/.env`时从`.env.example`复制，并生成本机随机`SECRET_KEY`；
3. 缺少`node_modules`时执行`npm ci`；
4. 本地数据库为空时自动建表并初始化：共享管理员`admin`（密码`00000000`）、演示站场、调车联锁表35条进路与六个实验专题18道题目。

各机器的数据库在本机生成，账号与作答数据相互独立、不随Git分发；每台机器首次启动都会自动创建同一个共享管理员账号`admin` / `00000000`。学生与教师账号可在登录页自行注册。需要真实AI调用时，编辑`framework/backend/.env`填写自己的`DEEPSEEK_API_KEY`。

默认前端为`http://127.0.0.1:5173/`，后端为`http://127.0.0.1:8000/`。教学数据初始化脚本`framework/backend/scripts/seed_local_data.py`可单独重跑；已有专题1—4按标准站发布新版，保留历史作答快照和管理员编辑内容。旧功能数据清理前自动生成本机恢复备份，见 [本次调整](docs/study-space-2026-11-15.md)。

手动准备（仅当自动步骤失败需要排查时）：

```powershell
python -m venv .runtime/venv
.runtime/venv/Scripts/python.exe -m pip install -r framework/backend/requirements.lock.txt
npm --prefix framework/frontend ci
Copy-Item framework/backend/.env.example framework/backend/.env
```

`.env.example`不包含可用密钥，勿将实际配置提交到Git。管理员初始化及资料导入详见`接管与使用说明.md`、`调车联锁表数据库导入说明.md`与`管理员出题与批阅使用说明.md`。

