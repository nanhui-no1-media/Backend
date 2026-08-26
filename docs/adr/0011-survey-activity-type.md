# 调研作为第四种活动类型

日期：2026-08-26

活动表已按 [ADR 0007](0007-activity-independent.md) 用 `type` 区分众议 / 征集 / 展示。需要第四种窗口——**调研**：填一份问卷，而不是投票或收作品。加入流程里的**自我介绍问卷**已按 [ADR 0009](0009-portal-review-about-tutorials.md) 把 SurveyJS 嵌进本库；调研复用同一插件与同一套 Schema/作答落库方式，不另起服务。

## 决策

1. **同一 `Activity` 表，`type=survey`。** 生命周期与众议相同：`scheduled → open → closed`（可排期；到 `end_at` 惰性关闭）。不并入 `recruitment` 的自我介绍问卷（那是加入流程单例，不是活动）。
2. **受众按份调研配置**：`public`（访客可列/开/交）或 `members`（须登录）。创建后不可改。其他活动类型仍仅成员可见（首页 feed 对众议/征集/展示的标题泄漏保持原样）。
3. **作答规则**：已登录用户每份调研一行（部分唯一约束 `(activity, user)` where `user` is not null）；访客 `user=null`、不限次数。不按 cookie 去重。
4. **Schema 可改窗口**：待开始，或已开放但尚无作答。标题/正文/时间仍只在待开始可改（现有 `can_edit`）。第一份作答之后问卷锁定。
5. **访问控制不拆新权限**（[ADR 0005](0005-access-control-principle.md)）：创建仍是 `add_activity` + 已验证；改仍是发起人 OR `change_activity`；结果只在 Django admin 用模型权限看。前端不新增 `can_*`。调研不算社团义务，不进收件箱债。
6. **门户只填、不看结果。** 详情给 `schema` / `my_response` / `response_count`，不给作答列表；图表与 Creator 看板走 Django admin（后续切片）。

## 被否的方案

- **把加入问卷迁进活动表**：加入是招生单例，与可排期、可审核公开的调研窗口不是同一概念。
- **新命名权限 / `can_*`**：看结果的持有者就是能进 admin 的人，不满足 ADR 0005 拆权三条。
- **Cookie 访客去重**：不可靠且超出本切片；访客可重复提交是刻意取舍。
