# 附件创建接缝：create 是接口，HTTP / tus / 活动是适配器

日期：2026-08-27

统一附件已按 [ADR 0002](0002-unified-attachment-endpoint-and-permission.md) 收口为 `POST /attachments/` + 抽象权限。之后又加了新闻父级、tus 可续传、以及活动的**作品** / **展品** 父级。创建路径散落在 HTTP 视图、tus 完成钩子、活动投稿/布展里，各自手写 FK。

## 决策

1. **`attachments/create.py` 是创建接缝。** 调用方只认 `create_attachment` / `copy_attachment` / `parent_of` 与父级注册表。谁能挂、FK 怎么填、复制怎么落地，都在这一处。
2. **`POST /attachments/` 与 tus 是增量适配器。** 只接受注册表里 `endpoint=True` 的父级（任务 / 申报 / 新闻）。一次一个文件、一个父级。
3. **活动批量是第二个适配器。** 征集 `submit`、展示 `_build_exhibit` / `update_exhibit` / `import_from_collection` 调同一套 create / copy。作品与展品 **不是** HTTP 父级。
4. **作品/展品不进 `POST /attachments/`。** 投稿与布展是原子批量（一束文件、一人一作品、展品与投票选项同步）。拆成增量上传会把「提交即锁定 / 布展成套」拆碎。权限与删除仍走统一 `DELETE /attachments/{id}/`（注册表含作品/展品）。

本 ADR **延伸** ADR 0002（统一端点 + 抽象权限），不废止它：增量端点仍在，权限规则仍是创建者 / 活跃参与者 / 管理权限；只是创建实现从「视图里手写 FK」收进 create 模块。

## 被否的方案

- **作品/展品也作为 HTTP 父级**（`submission_id` / `exhibit_id` 上传）：表面上接口更齐，但提交/布展的原子性与人数/文件数上限会漏到客户端拼装，且与「一人一作品、提交即锁定」冲突。
- **tus 走全部父级**：作品/展品没有增量续传需求；大文件仍可先落到任务/新闻，活动侧复制。
