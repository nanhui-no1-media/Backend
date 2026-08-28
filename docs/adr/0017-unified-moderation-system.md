# 统一审核系统：三套案件、一个职员入口

日期：2026-08-28

职员侧只应有一个**审核系统**入口。意见反馈曾寄存在 `proposals`（申报）里，与发布审核、身份审核并列却不在同一队列；「举报」又只是反馈的一个类别，没有对象、不能结案处置。本 ADR 把意见反馈吸收进 `reviews`，新增第一类举报案，然后删掉申报运行时。

## 决策

1. **审核系统是职员应用/入口，不是第四种案件。** `/reviews` 队列四张桌子：发布审核、意见反馈、举报案、身份审核（身份桌既有，保留）。桌子只在对应 `can_*` 为真时出现。
2. **三种案件是兄妹模型、各自状态机，不折进 `Review` 行。** `Review` 仍只表示「这条新闻/活动/教程可否公开」。`Feedback` 是无对象投递箱（待处理 → 已了结）。`ReportCase` + `ReportFiling` 是有对象调查票（进行中 → 驳回 / 成立并处置）。
3. **三个权限，不用组名分支。** `reviews.moderate`（发布审核，既有）、`reviews.view_feedback`（查看并了结意见反馈）、`reviews.handle_report`（处理举报案）。关闭反馈不另拆 approve 权限（持有者不会不同）。前端能力：`can_view_feedback` 改源、`can_handle_reports` 新增；去掉 `can_approve_proposals` / `can_change_proposals`。
4. **成立并处置是特权默认动作。** 视图只查 `reviews.handle_report`。`report_lifecycle.uphold` 按对象执行默认处置，**不**要求操作者同时持有 `reviews.moderate` / `messaging.manage_comment_thread` / `messaging.mute_user`：新闻/活动/教程 `apply(REMOVE)`（已下架则幂等只结案）；评论走 `delete_comment_for_report`（跳过 `can_manage_thread`）；用户走 `mute_user_for_report`（跳过 `mute_user` 权限；仍禁自禁、已禁言则拒；`ends_at` 省略即永久）。这两处特权函数只给 `report_lifecycle` 调用。不把评论区禁言 / 停用账号接到此按钮。恢复走既有重新上架 / 解除禁言。
5. **不要 GenericFK。** 举报对象与 `Review` / `CommentThread` 一样：可空 FK + 恰好一个父级的 CheckConstraint。进行中案每对象至多一张（五条部分唯一约束）。
6. **`proposals` 运行时删除，迁移包留作墓碑。** 数据：`Proposal` → `Feedback`（`pending_approval`→`pending`；`approved`/`rejected`/`withdrawn`→`closed`；类别 `report`→`complaint`）。附件 FK `proposal` → `feedback`。旧 `feedback_category=report` **不**自动生成举报案。`proposals` 仍在 `INSTALLED_APPS`，只留历史迁移；本变更不 squash、不卸 app。

## 被否的方案

- **把反馈/举报折进现有 `Review` 行**：`Review` 的语义是发布门控，混进去会让「可否公开」与「有人投诉了什么」无法分开查询与授权。否。
- **ContentTypes GenericFK**：与附件/审核/评论区既有「可空 FK + XOR」不一致，且不参与 CASCADE。否。
- **成立处置再查 moderate / mute_user**：处理举报的人与发稿审核/禁言的人可以不是同一批；再查会卡住默认处置。否。
- **本变更卸掉 `proposals` app / squash 迁移**：历史迁移链会断。否。
