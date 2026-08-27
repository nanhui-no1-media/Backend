# 问卷与问卷结果从活动表拆出

日期：2026-08-27

调研仍是 `Activity.type=survey` 窗口（排期 / 受众 / 审核），但 Schema 与作答不再住在活动表。[ADR 0011](0011-survey-activity-type.md) 把问卷塞进活动，后台编辑/统计也挂在活动页上；加入流程另有一套 `JoinQuestionnaire` / `JoinResponse`。两边其实是同一件事：一份问卷 + 一叠结果。公开调研还允许访客无限提交，有刷单空间。

## 决策

1. **`Questionnaire` + `QuestionnaireResponse` 落在 `activities` app**（不另起 app）。调研活动 `OneToOne` 指向一份 `kind=survey` 问卷；自我介绍是 `kind=join` 单例。门户调研页与加入页只投影 Schema / 收作答。
2. **编辑问卷与查看统计只挂问卷后台**（及问卷结果行上的统计链），不再出现在活动 change form。加入后台同样不再托管 Creator / 看板。单份作答在问卷结果后台用 SurveyJS display mode 阅读，不另做门户页。
3. **未登录作答绑定设备标识。** 门户生成 UUID 写入 localStorage，请求带 `X-Device-Id`。部分唯一约束 `(questionnaire, device_id)` where `user` is null。已登录仍按用户一行。浏览器清存储或换浏览器仍可再交——这是 Web 能做到的上限，不是硬件 ID。
4. **Schema 可改窗口不变**：待开始，或开放且该问卷尚无作答。

## 被否的方案

- **新 Django app**：问卷只服务活动调研与加入单例，独立 app 过重。
- **从活动类型里拿掉调研**：窗口（排期 / 受众 / 审核 / 列表）仍是活动该管的；拆的是表单与结果，不是窗口。
- **Cookie 去重 / 浏览器指纹**：Cookie 与 ADR 0011 已否的一样易清；指纹不稳定且隐私差。显式 UUID 可解释、可约束。
