# 活动从申报中独立（两类型模型 + 移除审批环节）

## 背景

`申报(Proposal)` 原是一张被复用的容器表，**同时装活动申报与意见反馈**：两者共享同一张表、同一套 `voting → pending_approval → approved/...` 状态机、同一个写死的"赞成/反对/弃权、一人一票" `Vote` 模型。

新需求把"活动"重新定义为两种类型——**众议**（可配置选项的投票）与**征集**（收作品的投稿箱）。两者与意见反馈的差异都被拉大：

- 众议要自定义选项、一人一票/一人多票可配、公开/秘密可配——旧 `Vote` 完全表达不了。
- 征集要开窗收作品、配置上传规则、一人一作品、事后录用/退稿——申报表里没有任何对应结构。
- 反馈仍是单向投递箱，与上述两者毫无共用生命周期可言。

继续把活动硬塞进申报表，类型条件分支只会越堆越多——正是 [ADR 0003](0003-no-shared-task-proposal-lifecycle-base) 当初想避免的味道。

此外，旧活动生命周期是"**先投票、再由社长审批活动计划**"。但在新语义下，众议的活动**就是**投票（票数即结果），征集的活动**就是**收件窗口（复审的是作品，不是活动计划）——"审批活动计划"这一环在两种新类型里都失去意义。

## 决策

1. **活动独立成第一类概念**：新建 `activities` app 与 `Activity` 模型，与 `申报` 分离。`申报` 退化为**仅承载意见反馈**的容器（反馈数据保留）。

2. **移除"审批活动计划"环节**：活动发起即对已验证成员开放，无审批门禁。`proposals.approve_proposal` 权限对活动失效。

3. **两类型模型**（同一 `Activity` 表，`type` 区分）：
   - **众议** = 可配置选项的投票：发起人自定义选项、配置每人最多选 `K` 项（`K=1` 即一人一票）、可选公开或**秘密**投票；截止按各选项计数结算。
   - **征集** = 收作品投稿箱：发起人配置允许后缀/单文件大小/单作品文件数/最大征集数量；**一人一作品**、提交即锁定；收件结束后由发起人或持复审权限者逐个复审为 录用/退稿。

## 访问控制（遵循 [ADR 0005](0005-access-control-principle)）

- 发起活动 / 投票 / 投稿 = **身份门禁**（已验证成员，[ADR 0006](0006-verification-model)），不单造权限。
- 征集复审 = **对象级**：`发起人 OR has_perm('activities.review_collection')`，叠加 lifecycle 守卫。`review_collection` 是本 app 唯一新增命名权限。
- 秘密票明细 = **仅 `is_superuser`**（平台唯一逃生舱；`is_staff` 不获得此能力）。
- 提前关闭活动 = `creator OR has_perm('activities.change_activity')`。
- 状态机守卫集中在 `activities/lifecycle.py`，与访问控制分离（遵循 [ADR 0003](0003-no-shared-task-proposal-lifecycle-base)）。

## 附件

作品文件复用统一附件系统（[ADR 0001](0001-unified-attachment-nullable-fks) / [0002](0002-unified-attachment-endpoint-and-permission.md)），为 `Attachment` 增加 `submission` 父类型（可空 FK + 更新"恰好一个父级"约束）。大文件走 tus 续传（[ADR 0004](0004-feedback-media-tus-resumable-upload.md)）。

## 被否的方案

- **维持共享申报表**（活动仍是 `proposal_type=activity`，内部再分众议/征集）：复用最省事，但众议/征集/反馈三者字段与生命周期各异，类型条件分支会持续堆积，违背"深模块"与 ADR 0003 的初衷。
- **保留"开放前需社长审批"**：与"活动 = 投票/收件"的语义摩擦——票数/作品本身就是结果，再叠一层计划审批是多余的门禁。
- **评奖 / 等级 / 排名选择(STV) / 加权投票**：超出"录用/退稿"与"最多选 K 项"的最小够用模型，属范围蔓延； secret ballot 之外的"可配置受众"同理。

## 后果

- 一次数据迁移：清空旧 `activity` 行、保留 `feedback`；`proposals` 移除活动专属字段（`location`/`expected_participants`/`budget`/`planned_date`/`activity_type`）与活动侧 `Vote` 模型（SQLite dev-only，数据清零）。
- 前端移除旧活动申报入口，新增活动（众议/征集）入口与渲染（正文升至新闻同级富文本）。
- 旧 `can_approve_proposals` 能力投影对活动失效（反馈若仍走审则保留其反馈语义）。
