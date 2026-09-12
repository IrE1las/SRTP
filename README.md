# SRTP 铁路联锁实训

Vue 3 前端与 FastAPI 后端组成的铁路联锁教学网站，包含站场交互作答、经典例题错误解释、实验专题、教师出题与批阅等功能。

## 项目资料

- `framework/frontend`：网页与站场图形交互。
- `framework/backend`：登录、题目、判分与AI解析接口。
- `ai_design/station`：专业规则、站场拓扑、核对后的联锁表和题目依据。
- `pictures`：站场原图等项目图片。
- `车站与区间控制实验`中的四份报告：实验专题会校验这些来源文件的哈希，不能单独修改原件后继续沿用旧题目。

专业解释以本项目已有规则文件为最高约束。详细操作见根目录的各项功能说明。

## 首次运行

需要Python 3.12+及Node.js/npm（Windows）。

双击根目录`启动项目.bat`（或运行`启动项目.ps1`）即可，启动器会自动完成本机首次准备，之后每次启动也会自动检查：

1. 创建`.runtime/venv`虚拟环境，并按`framework/backend/requirements.lock.txt`安装后端依赖（锁文件更新时自动重装）；
2. 缺少`framework/backend/.env`时从`.env.example`复制，并生成本机随机`SECRET_KEY`；
3. 缺少`node_modules`时执行`npm ci`；
4. 本地数据库为空时自动建表并初始化：共享管理员`admin`（密码`00000000`）、演示站场、调车联锁表35条进路与实验专题24道题目。

各机器的数据库在本机生成，账号与作答数据相互独立、不随Git分发；每台机器首次启动都会自动创建同一个共享管理员账号`admin` / `00000000`。学生与教师账号可在登录页自行注册。需要真实AI调用时，编辑`framework/backend/.env`填写自己的`DEEPSEEK_API_KEY`。

默认前端为`http://127.0.0.1:5173/`，后端为`http://127.0.0.1:8000/`。教学数据初始化脚本`framework/backend/scripts/seed_local_data.py`可单独重跑（幂等，已有数据时自动跳过）。

手动准备（仅当自动步骤失败需要排查时）：

```powershell
python -m venv .runtime/venv
.runtime/venv/Scripts/python.exe -m pip install -r framework/backend/requirements.lock.txt
npm --prefix framework/frontend ci
Copy-Item framework/backend/.env.example framework/backend/.env
```

`.env.example`不包含可用密钥，勿将实际配置提交到Git。管理员初始化及资料导入详见`接管与使用说明.md`、`调车联锁表数据库导入说明.md`与`管理员出题与批阅使用说明.md`。

## 团队协作

每完成并验证一个功能后，将改动提交到个人功能分支，推送后创建以`main`为目标的Pull Request，由团队审阅合并。开始新功能前先获取远端最新提交；遇到同伴改动先检查差异，不用强制推送覆盖共享分支。

示例分支名：`codex/功能名称`。`main`只接收已审阅的整合结果。分支是代码协作单位，不进行每次保存文件时的自动上传。

仓库不包含本地密钥、用户数据库、浏览器登录状态、依赖目录、构建缓存、备份及本机验证截图。`.planning/`与`outputs/`中的记录只存在于各开发者本机，历史说明中对它们的引用不代表这些文件已上传。与网站运行无关的第三方课程可执行软件也不上传。

前端验证：`npm --prefix framework/frontend run build`。后端验证：在`framework/backend`目录使用已安装依赖的Python运行`python -m pytest tests -q`；验证前须配置测试运行所需的本地`.env`。
