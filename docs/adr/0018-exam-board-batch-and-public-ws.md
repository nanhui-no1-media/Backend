# 考试看板：批次课表 + 公开 WebSocket 误刊广播

日期：2026-08-30 · 与 jinha 协作

考试看板原先是扁平 `ExamData`（日期 / 标题 / 科目逗号串），前端用 localStorage 自管课表，与后端未接通。教室大屏需要：一场考试含多日、多科目、中间有休息；按**批次**切课表；考试中广播**题目误刊**（图+文），所有打开的看板立刻刷新。

## 决策

1. **考试 → 批次 → 科目场次。** `Exam` 有标题；`ExamBatch` 是一条课表（高一 / 高二）；`ExamSubject` 带日期 + 起止时刻。间隙不建模，由看板按墙钟判定「休息」。同一批次同一日科目不得重叠；相邻（结束=下一场开始）允许。
2. **写权限仍是 Django 白送的 `exam_board.add_exam`。** 能力键 `can_manage_exam` 不变。误刊发布/撤回不拆新权限（同一批信息组，无独立审计需求）。读（课表、授时、当前误刊、看板 socket）匿名开放。
3. **公开 WebSocket `/ws/exam-board/`。** 访客可连，进组 `exam_board`。只推不收业务数据。事件：`exam`（课表变更）、`errata`（新误刊 payload）、`errata_cleared`。HTTP 仍是事实源；重连后客户端再拉课表与 `GET /exam_board/errata/current/`。不占用 `/ws/messaging/`，不要求登录——教室大屏是匿名页。
4. **授时走本站。** `GET /exam_board/exams/clock/` 返回 Asia/Shanghai 墙钟；不再调淘宝/苏宁。科目日期与时刻按上海解读（全局 `TIME_ZONE` 仍为 UTC）。
5. **误刊挂在一场考试上，可同时多条。** 新发布不再撤回旧的。图片走 `ImageField`（jpeg/png/gif/webp，≤5MB）。到期时刻跟该考试上海墙钟上的科目场次走；`GET current?exam=` 遇过期按 id 升序撤回并广播 `errata_cleared`（带 `ids`），看板依次收走。

本 ADR **扩展** [ADR 0015](0015-channels-without-redis.md)：messaging socket 仍要登录；考试看板是第二条、匿名的只推通道。v1 仍是单 ASGI worker + `InMemoryChannelLayer`。挤号、横幅公告路径不变。

## 被否的方案

- **继续扁平 `exam_list` 字符串**：无法表达多日、休息、批次。否。
- **误刊走 messaging 私信/通知**：教室大屏无登录、要全员同屏，不是投给某用户。否。
- **误刊走横幅公告**：横幅是全站顶栏短讯且访客靠轮询；误刊要大图+即时弹出。否。
- **把误刊挂统一 Attachment**：XOR 父级约束要再加一列，误刊又是短命广播。否。
- **科目时刻用 DateTimeField UTC**：教室课表是上海墙钟；与全局 UTC 设置解耦更安全。否。

## 后果

- 信息组获 `add/change/delete_exam`（迁移 0004 从 `*_examdata` 换过来）。
- Nginx 不必按路径拆 `/ws/`：`/ws/exam-board/` 与 `/ws/messaging/` 同一段 Upgrade。
