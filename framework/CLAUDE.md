# 铁路联锁仿真练习系统 \- 完整项目开发计划

## 项目概述

**项目名称**：铁路计算机联锁仿真实训系统（B/S 架构）

**技术栈**：

- **前端**：Vue3 \+ Vite \+ Element Plus \+ Canvas/SVG（站场图绘制）

- **后端**：FastAPI \+ SQLAlchemy \+ SQLite/MySQL

- **AI 评分**：DeepSeek API

- **架构**：纯 B/S 前后端分离

**核心目标**：为铁道信号专业师生提供在线联锁操作实训平台，支持学生进行进路办理、信号操作练习，AI 自动分析操作日志并智能评分。

---

## 第一部分：系统整体架构设计

### 1\.1 系统模块划分

```Plain Text
railway-interlocking-system/
├── frontend/                 # Vue3前端
│   ├── src/
│   │   ├── views/
│   │   │   ├── student/      # 学生端页面
│   │   │   ├── teacher/      # 教师端页面
│   │   │   └── auth/         # 登录认证
│   │   ├── components/
│   │   │   ├── StationCanvas/ # 站场图核心组件（SVG/Canvas）
│   │   │   └── common/
│   │   ├── store/            # Pinia状态管理
│   │   ├── router/           # 路由
│   │   └── utils/
│   └── package.json
│
├── backend/                  # FastAPI后端
│   ├── app/
│   │   ├── api/              # 接口路由
│   │   ├── models/           # 数据库模型
│   │   ├── schemas/          # Pydantic数据模型
│   │   ├── services/         # 业务逻辑
│   │   │   ├── interlocking/ # 联锁核心逻辑引擎
│   │   │   ├── ai_scoring/   # AI评分服务
│   │   │   └── exercise/     # 练习管理
│   │   └── core/             # 配置、认证、数据库
│   └── main.py
│
└── docs/                     # 联锁表、站场配置数据
```

### 1\.2 核心功能清单

|模块|功能点|优先级|
|---|---|---|
|**用户系统**|登录 / 注册、角色权限（学生 / 教师 / 管理员）|P0|
|**站场仿真**|SVG 站场图渲染、信号机 / 道岔 / 区段状态显示|P0|
|**联锁逻辑**|进路办理、取消、解锁、道岔单操、信号开放检查|P0|
|**练习系统**|教师出题、学生答题、联锁表对照练习|P0|
|**操作日志**|完整记录学生每一步操作（点击、时间、状态）|P0|
|**AI 评分**|DeepSeek 分析日志、多维度评分、智能评语|P0|
|**成绩管理**|成绩查询、统计分析、错题回顾|P1|
|**题库系统**|联锁表题库、自定义练习场景|P1|
|**故障模拟**|道岔故障、信号故障、区段故障模拟|P2|

---

## 第二部分：数据库设计（核心表结构）

### 2\.1 用户与权限表

```sql
-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(50),
    role VARCHAR(20) NOT NULL, -- 'student', 'teacher', 'admin'
    student_id VARCHAR(30),
    class_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2\.2 站场配置表（核心）

```sql
-- 车站配置表
CREATE TABLE stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_name VARCHAR(100) NOT NULL, -- 如"成都东站上行咽喉"
    station_code VARCHAR(50),
    description TEXT,
    station_config JSON NOT NULL, -- 站场图SVG配置、设备坐标
    created_at TIMESTAMP
);

-- 信号机表
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER,
    signal_code VARCHAR(20) NOT NULL, -- X, S, D1, D2...
    signal_type VARCHAR(20), -- 'train', 'shunting'
    position_x INTEGER,
    position_y INTEGER,
    direction VARCHAR(10), -- 'up', 'down', 'left', 'right'
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

-- 道岔表
CREATE TABLE switches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER,
    switch_code VARCHAR(20) NOT NULL, -- 1#, 2#, 3#...
    switch_type VARCHAR(20), -- 'single', 'double'
    normal_position VARCHAR(10), -- 'left', 'right'
    position_x INTEGER,
    position_y INTEGER,
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

-- 轨道区段表
CREATE TABLE sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER,
    section_code VARCHAR(20) NOT NULL, -- IAG, 1DG, 2DG...
    section_type VARCHAR(20),
    FOREIGN KEY (station_id) REFERENCES stations(id)
);
```

### 2\.3 联锁表与题库

```sql
-- 联锁表
CREATE TABLE interlocking_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER,
    route_name VARCHAR(100) NOT NULL, -- 进路名称
    entry_signal VARCHAR(20), -- 始端信号机
    exit_signal VARCHAR(20), -- 终端信号机
    route_type VARCHAR(20), -- 'receive', 'departure', 'shunting'
    switches_required JSON, -- 道岔要求：{"1":"normal", "2":"reverse"}
    sections_occupied JSON, -- 占用区段
    hostile_signals JSON, -- 敌对信号
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

-- 练习题表
CREATE TABLE exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER,
    station_id INTEGER,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    exercise_type VARCHAR(30), -- 'route_arrange', 'signal_practice', 'troubleshooting'
    target_routes JSON, -- 目标进路列表
    time_limit INTEGER, -- 限时（秒）
    difficulty VARCHAR(20), -- 'easy', 'medium', 'hard'
    scoring_rules JSON, -- 评分规则配置
    created_at TIMESTAMP
);
```

### 2\.4 练习记录与操作日志

```sql
-- 练习会话表
CREATE TABLE exercise_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    exercise_id INTEGER,
    station_id INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    total_time INTEGER, -- 总耗时（秒）
    total_clicks INTEGER,
    valid_clicks INTEGER,
    invalid_clicks INTEGER,
    status VARCHAR(20), -- 'ongoing', 'completed', 'timeout'
    final_score DECIMAL(5,2),
    ai_analysis TEXT,
    created_at TIMESTAMP
);

-- 操作日志表（核心！用于AI评分）
CREATE TABLE operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operation_type VARCHAR(30), -- 'click_signal', 'click_switch', 'click_button', 'keyboard'
    target_code VARCHAR(50), -- 操作对象：X, S, 1#, D1...
    target_type VARCHAR(20), -- 'signal', 'switch', 'section', 'button'
    operation_result VARCHAR(20), -- 'success', 'failed', 'invalid', 'hostile'
    state_before JSON, -- 操作前状态
    state_after JSON, -- 操作后状态
    error_message VARCHAR(200),
    time_spent_ms INTEGER, -- 本次操作耗时
    FOREIGN KEY (session_id) REFERENCES exercise_sessions(id)
);

-- AI评分结果表
CREATE TABLE ai_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    accuracy_score DECIMAL(5,2), -- 正确率得分
    efficiency_score DECIMAL(5,2), -- 效率得分
    operation_quality DECIMAL(5,2), -- 操作质量（瞎点率）
    total_score DECIMAL(5,2), -- 总分
    ai_comment TEXT, -- AI评语
    wrong_operations JSON, -- 错误操作分析
    suggestions JSON, -- 改进建议
    deepseek_response JSON, -- 原始API返回
    created_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES exercise_sessions(id)
);
```

---

## 第三部分：分阶段开发计划（给 Claude Code 执行）

### 🎯 阶段一：项目基础搭建（预计 2\-3 小时）

**目标**：完成前后端项目初始化、基础架构、用户系统

#### 3\.1\.1 后端 FastAPI 搭建

```bash
# 1. 创建后端项目结构
mkdir -p backend/app/{api,models,schemas,services,core}
cd backend

# 2. 安装依赖
pip install fastapi uvicorn sqlalchemy pydantic python-jose[cryptography] passlib[bcrypt] python-multipart python-dotenv openai

# 3. 创建核心文件
# - backend/app/core/config.py       # 配置管理
# - backend/app/core/database.py     # 数据库连接
# - backend/app/core/security.py     # JWT认证、密码哈希
# - backend/app/models/user.py       # 用户模型
# - backend/app/schemas/user.py      # 用户Schema
# - backend/app/api/auth.py          # 认证接口
# - backend/main.py                  # 入口文件
```

#### 3\.1\.2 前端 Vue3 搭建

```bash
# 1. 创建Vue3项目
npm create vite@latest frontend -- --template vue
cd frontend

# 2. 安装依赖
npm install element-plus axios pinia vue-router@4 @element-plus/icons-vue

# 3. 项目结构初始化
# - src/router/index.js        # 路由配置（学生/教师/登录）
# - src/store/user.js          # 用户状态管理
# - src/utils/request.js       # axios封装
# - src/views/auth/Login.vue   # 登录页
# - src/layout/                # 布局组件
```

**阶段一验收标准**：

- ✅ 后端启动正常，API 文档可访问

- ✅ 用户注册、登录、JWT 认证功能正常

- ✅ 前端路由守卫、权限控制生效

- ✅ 师生角色区分，不同角色看到不同菜单

---

### 🎯 阶段二：联锁核心逻辑引擎（预计 4\-5 小时）

**目标**：实现 6502 电气集中联锁核心逻辑，这是整个系统的灵魂

#### 3\.2\.1 联锁逻辑引擎开发

```python
# backend/app/services/interlocking/engine.py

class InterlockingEngine:
    """6502电气集中联锁核心引擎"""
    
    def __init__(self, station_id):
        self.station_id = station_id
        self.state = {
            'signals': {},      # 信号机状态: {'X': 'closed', 'S1': 'open'}
            'switches': {},     # 道岔状态: {'1': 'normal', '2': 'reverse'}
            'sections': {},     # 区段状态: {'IAG': 'clear', '1DG': 'occupied'}
            'routes': [],       # 已建立进路
            'locked_routes': [] # 已锁闭进路
        }
    
    def check_route_conditions(self, entry_signal, exit_signal):
        """检查进路办理条件（联锁三大条件）"""
        # 1. 检查道岔位置正确
        # 2. 检查区段空闲
        # 3. 检查敌对进路未建立
        # 4. 检查信号机未开放
        pass
    
    def arrange_route(self, entry_signal, exit_signal):
        """办理进路：选路→锁闭→开放信号"""
        # 1. 选路阶段：选择道岔位置
        # 2. 转换道岔到规定位置
        # 3. 检查联锁条件
        # 4. 进路锁闭
        # 5. 开放信号
        pass
    
    def cancel_route(self, signal_code):
        """取消进路"""
        pass
    
    def manual_unlock(self, section_code):
        """人工解锁"""
        pass
    
    def operate_switch(self, switch_code, target_position):
        """单操道岔"""
        # 检查道岔是否在进路中被锁闭
        pass
    
    def check_hostile_routes(self, entry, exit):
        """检查敌对进路"""
        pass
```

#### 3\.2\.2 标准站场数据预置

- 预置 "下行咽喉标准站" 配置（信号机：X、S、D1\-D10，道岔：1\#\-10\#，区段：IAG、1DG\-10DG）

- 预置完整联锁表（接车进路、发车进路、调车进路共 20 \+ 条）

**阶段二验收标准**：

- ✅ 办理 X→I 道接车进路，道岔自动转到正确位置

- ✅ 进路锁闭后，道岔无法单操

- ✅ 敌对进路无法同时建立

- ✅ 区段占用时信号自动关闭

- ✅ 取消进路、人工解锁功能正常

---

### 🎯 阶段三：站场图 SVG 可视化组件（预计 3\-4 小时）

**目标**：实现可交互的铁路站场图，这是学生操作的核心界面

#### 3\.3\.1 SVG 站场图组件开发

```vue
<!-- frontend/src/components/StationCanvas/StationCanvas.vue -->
<template>
  <svg class="station-canvas" @click="handleCanvasClick">
    <!-- 轨道线路 -->
    <g class="tracks">
      <line v-for="track in tracks" :key="track.id" />
    </g>
    
    <!-- 道岔组件 -->
    <g class="switches">
      <SwitchComponent 
        v-for="sw in switches" 
        :key="sw.code"
        :code="sw.code"
        :position="sw.position"
        :state="currentState.switches[sw.code]"
        @click="handleSwitchClick(sw.code)"
      />
    </g>
    
    <!-- 信号机组件 -->
    <g class="signals">
      <SignalComponent
        v-for="sig in signals"
        :key="sig.code"
        :code="sig.code"
        :type="sig.type"
        :state="currentState.signals[sig.code]"
        @click="handleSignalClick(sig.code)"
      />
    </g>
    
    <!-- 轨道区段 -->
    <g class="sections">
      <SectionComponent
        v-for="sec in sections"
        :key="sec.code"
        :code="sec.code"
        :state="currentState.sections[sec.code]"
      />
    </g>
    
    <!-- 进路高亮显示 -->
    <g class="routes-highlight"></g>
  </svg>
</template>

<script setup>
// 核心逻辑：
// 1. WebSocket/轮询同步后端联锁状态
// 2. 点击信号机/道岔发送操作请求
// 3. 实时渲染状态变化
// 4. 记录每一步操作到本地缓存
</script>
```

#### 3\.3\.2 状态同步机制

- 前端操作 → 发送到后端联锁引擎 → 后端计算新状态 → 返回前端渲染

- 操作日志实时记录到数据库

**阶段三验收标准**：

- ✅ 站场图清晰显示信号机、道岔、轨道区段

- ✅ 点击始端 \+ 终端信号机可办理进路

- ✅ 进路建立后有高亮显示

- ✅ 道岔定反位、信号机开闭有明显视觉反馈

- ✅ 区段占用 / 空闲状态区分明显

---

### 🎯 阶段四：练习系统与操作日志（预计 3\-4 小时）

**目标**：实现教师出题、学生练习、完整操作记录

#### 3\.4\.1 教师端功能

- 练习题库管理：创建、编辑、删除练习题

- 题目配置：选择车站、设置目标进路、限时、难度

- 班级管理：查看学生练习情况、成绩统计

#### 3\.4\.2 学生端功能

- 练习大厅：查看可用练习题

- 练习界面：站场图 \+ 题目要求 \+ 计时器 \+ 操作面板

- 练习历史：查看历史记录、错题回顾

#### 3\.4\.3 操作日志记录（重中之重！）

每一次学生操作都必须完整记录：

```javascript
// 前端操作拦截器
const logOperation = async (operation) => {
  const logEntry = {
    session_id: currentSession.value.id,
    operation_type: operation.type,
    target_code: operation.target,
    target_type: operation.targetType,
    operation_result: operation.result,
    state_before: JSON.stringify(prevState),
    state_after: JSON.stringify(newState),
    error_message: operation.error,
    time_spent_ms: Date.now() - operation.startTime
  }
  // 发送到后端保存
  await api.post('/operation-logs', logEntry)
}
```

**阶段四验收标准**：

- ✅ 教师可创建 "办理 X 至 I 道接车进路" 练习题

- ✅ 学生进入练习，计时器开始计时

- ✅ 学生每一次点击都被记录到数据库

- ✅ 完成练习后自动结束会话

- ✅ 可查看历史练习的完整操作回放

---

### 🎯 阶段五：DeepSeek AI 智能评分（预计 3\-4 小时）

**目标**：实现 AI 多维度智能评分，这是系统核心亮点

#### 3\.5\.1 AI 评分 Prompt 工程（核心）

```python
# backend/app/services/ai_scoring/scoring_service.py

class AIScoringService:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
    
    def generate_score(self, session_id):
        # 1. 获取完整操作日志
        logs = OperationLog.filter(session_id=session_id).order_by('timestamp')
        exercise = Exercise.get(id=session.exercise_id)
        
        # 2. 构建专业Prompt
        prompt = f"""
【角色】你是一位资深铁路信号专业教授，正在评鉴学生的联锁操作练习。

【练习题目】{exercise.title}
【目标任务】{exercise.description}
【标准操作步骤】根据联锁表，正确操作为：{exercise.standard_steps}

【学生完整操作日志】（按时间顺序）
{self.format_logs(logs)}

【评分维度与规则】
1. 正确率（40分）：
   - 正确完成所有操作：40分
   - 每一处错误操作扣1-5分（误操作敌对信号、错误道岔、违规解锁等）
   - 遗漏关键步骤每处扣8分

2. 操作效率（30分）：
   - 标准耗时的1.5倍内完成：30分
   - 每超时30秒扣3分
   - 思考时间过长酌情扣分

3. 操作规范性（30分）：
   - 无无效点击、无瞎点：30分
   - 瞎点率（无效点击/总点击）>20%扣10分
   - 操作顺序混乱扣5-15分

【输出要求】
严格返回JSON格式，不要任何额外文字：
{{
  "accuracy_score": 分数,
  "efficiency_score": 分数,
  "operation_quality": 分数,
  "total_score": 总分,
  "ai_comment": "专业、详细的评语，指出优点和不足",
  "wrong_operations": [
    {{"time": "时间", "operation": "操作内容", "error": "错误分析"}}
  ],
  "suggestions": ["改进建议1", "改进建议2"]
}}
"""
        
        # 3. 调用DeepSeek API
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        # 4. 解析并保存结果
        return self.parse_and_save_result(response, session_id)
```

#### 3\.5\.2 评分结果展示

- 雷达图展示三个维度得分

- 错误操作逐条列出，带时间戳和分析

- AI 专业评语

- 改进建议

**阶段五验收标准**：

- ✅ 练习完成后自动触发 AI 评分

- ✅ 评分结果准确，错误操作识别正确

- ✅ AI 评语专业，符合铁路信号专业要求

- ✅ 瞎点率、超时等扣分逻辑正确

- ✅ 评分结果可持久化保存和查询

---

###  阶段六：成绩管理与系统优化（预计 2\-3 小时）

**目标**：完善系统功能，优化用户体验

#### 3\.6\.1 成绩统计分析

- 学生个人成绩趋势

- 班级整体成绩分布

- 将前端向用户展示的变量名英文翻译为中文（如ongoing,operate_switch等）

#### 3\.6\.2 联锁表学习功能

- 联锁表查询展示

- 进路与联锁表对照

- 敌对进路关系可视化

#### 3\.6\.3 系统优化

- 性能优化

- 修复bug，我发现的bug有：右上角倒计时失效

- 异常处理和错误提示

-请增加管理员可以管理（删除和改变）老师和学生产生的数据等,可以查看数据库，可以管理人员如删除账号等
---