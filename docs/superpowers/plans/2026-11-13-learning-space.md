> 当前产品范围以2026-11-15的 `实验专题题库说明.md` 和 AGENTS.md 当前执行覆盖为准。

# 学习空间整合与实验教学记录

**目标：** 学习导航依次为客观题库、实验专题、仿真操作台；原练习历史升级为实验学习记录，呈现学生操作、评分、错误及教学反馈。

**方案与约束：**
- 记录入口单独置于“学习记录”组，名称“实验学习记录”。旧路由保持可访问，不删除原功能。
- 只读取当前账号记录；教师预览有标记。不暴露进行中考核的评分条件。无评分标准的自由操作不生成虚构分数，规则反馈、AI解析、教师评语分开标识。
- 不修改原实验、联锁表、客观题和答案，不迁移覆盖旧数据库；不推送受旧密钥历史约束的分支。

**接口约定：**
`GET /api/learning-records?kind=all|dynamic|lab|simulation|classic|legacy&page=1&limit=20` 返回 `{items,total,counts}`。记录项含 `key,record_id,kind,kind_label,title,status,status_label,started_at,updated_at,operation_count,error_count,score,score_max,score_label,preview,continue_path`。

`GET /api/learning-records/{kind}/{record_id}` 返回同一记录及 `operations:[{id,sequence,time,action,target,accepted,message}],errors:[{label,message,correction,devices,operation_id}],feedback:[{source,title,text,time}]`。可额外提供状态快照和分项评分供回放查看。未评分用null，不以0代替。

**实施：**
- [x] 后端聚合和独立存储；自由仿真与经典图形的记录钩子；按账号隔离与考核保密测试。
- [x] 导航与统一实验入口；原入口兼容，修复依赖旧导航分组的页面。
- [x] 实验学习记录列表、筛选、详情时间线、错误与反馈、继续或回放入口。
- [x] 前后端测试、生产构建、实际浏览器检查及代码复核。


**复核：** 独立复核尝试因代理额度限制未完成，实施者完成了接口、权限、路由、数据与浏览器复核；不把此项记为独立审查通过。
