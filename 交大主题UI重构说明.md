# 西南交通大学主题 UI 重构

完成日期：2026-09-09。工程位置：D:\GitHub\SRTP。

## 查看与启动

- 本机预览：[实训平台](http://127.0.0.1:5173/)。
- 后续双击项目根目录「启动项目.bat」，使用原有实训账号。
- 升级现有 Vue 3 / Element Plus 前端，未新建独立校史站，未部署到公网。

## 官网来源与设计取舍

实际浏览了[校史文化](https://www.swjtu.edu.cn/xxgk/xswh.htm)、[学校首页](https://www.swjtu.edu.cn/)和[总体介绍](https://www.swjtu.edu.cn/xxgk/ztjs.htm)。

| 提取元素 | 来源与使用方式 |
| --- | --- |
| 深蓝与交大蓝 | 官网 style/public.css 的 #093278、#0075b7，用于品牌栏、主按钮、导航和主题变量 |
| 白底与浅色留白 | 提炼官网蓝白关系，简化为白色导航、浅灰工作区、轻边框卡片 |
| 校徽与书法校名 | [官方原图](https://www.swjtu.edu.cn/images/logo.png)，保留原图比例与内容 |
| 校门全景 | [官方内页头图](https://www.swjtu.edu.cn/images/0513ban1.png)，用于登录页及概览横幅 |
| 学校精神 | “竢实扬华、自强不息”，来自学校官方介绍 |
| 十六字校训 | “精勤求学、敦笃励志、果毅力行、忠恕任事”，来自校史文化页，放置于导航底部 |

辅助金色 #c6aa70 是本次设计的柔化点缀，不宣称为官方标准色。“知行致远”“以知促行，学以致用”等是页面设计文案，未标记为官方校训。素材原图存于 framework/frontend/public/brand，页面保留官网及文化页来源链接；图片与校徽权利属于原权利人。

## 完成内容

- 登录/注册：校园背景、书法标题、清晰表单；保留账号字段、角色与原认证接口，补充错误凭据反馈和防重复提交。
- 公共布局：深蓝校名栏、按角色分组导航、当前页标识、页面搜索、账户退出和手机抽屉导航。
- 学生/教师/管理员概览：校园横幅、真实统计数据、专项或教学任务入口。
- 练习大厅：经典专项与教学练习切换、名称/专题检索、空结果状态，原教学练习入口继续可用。
- 四道经典题：统一标题、选项卡、操作面板和提交按钮；保留设备状态色、完整站场和答案交互范围。
- 窄屏：表格和大站场在容器内查看，修复联锁表学习、回放和练习编辑器的固定宽度问题；手机保留文字辅助作答。

## 验证证据

验证产物位于 .planning/2026-09-09-swjtu-ui。

- build-report.txt：最终生产构建成功，现有 VueUse 注释和大体积主包提示仍在。
- ui-report.json：真实管理员登录、13 个页面导航；表单校验、错误密码反馈、页面搜索、练习过滤、手机导航和退出通过，无页面运行错误。
- regression/browser-report.json：四道经典题均通过完整 SVG 设备操作输入正确答案，并由真实后端判定通过。四题具有同一套设备；漏选/多选、题设道岔可选、错误定位、缩放拖动、键盘与图文同步通过。
- AI 解析链路本轮使用明确标记的测试响应验证请求和文本渲染，没有再次调用外部模型，也不作为模型内容质量验收。
- mobile-final-report.json：390px 窗口标题排版、文字辅助作答同步、真实提交及错误结果验证通过。
- change-manifest.json：15 个前端源文件新增/修改记录；ClassicExam.vue 的业务脚本与备份一致。站场领域文件 classicStation.js 的前后 SHA-256 一致。

页面导航验收使用管理员账号，本轮未创建学生/教师新账号、删除用户、变更 AI 密钥或修改专业答案资料。

## 文件与备份

- framework/frontend/src/style.css：全站主题与响应式样式。
- framework/frontend/src/layout/：校名栏、主导航、用户菜单。
- framework/frontend/src/ui/navigation.js：按角色提供导航及搜索项。
- framework/frontend/src/views/auth/Login.vue：登录与注册。
- framework/frontend/src/views/student/ExerciseLobby.vue：练习大厅。
- framework/frontend/src/components/CampusBanner.vue、PracticePath.vue：校园横幅与专项入口。

修改前的 src 与 index.html 已保存到 .backups/2026-09-09-swjtu-ui。备份未覆盖既有备份，原有未提交改动未清理。需要恢复时先停止项目，再将备份中的对应源码恢复到前端原位置；新组件在恢复原入口后不会被使用。
