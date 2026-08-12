# 展品布展入口从创建表单挪到详情页 — 设计

## 背景

展示(exhibition)活动的展品录入,目前在**创建表单**里(`ActivityFormPage` 展示分支:展品标题 + 文件上传,「创建时录入、创建后冻结」)。本设计把展品管理入口**从创建表单挪到详情页**,并恢复此前(#53/#54 移除的)「从征集导入」能力,放在详情页。

## 目标行为变化

展品从「创建时录入、创建后冻结」改为「**详情页在待开始期间录入/编辑/删除/导入,开放后冻结**」。展品成为一个在待开始期由策展人完整管理的子资源。

### 时间线

| 状态 | 策展人对展品 | 成员 |
|---|---|---|
| 待开始 scheduled | **可加 / 删 / 改 / 导入**(详情页管理面板) | 可预览,不能赞踩 / 投票 |
| 展示中 open | 冻结 | 可赞踩;启用投票时投票 |
| 已结束 closed | 冻结 | 只读 |

**冻结语义**:进入 open 后,`add_exhibit` / `update_exhibit` / `delete_exhibit` / `import_from_collection` 四个动作一律拒绝。投票一致性因此自动保证——只在没人投票时(scheduled 期)允许改选项。

**0 展品可创建**:创建展示不再要求至少 1 个展品;可以建出来先空着,策展人事后在详情页布展。

## 后端动作

四个命名 detail action,挂在 `ActivityViewSet`,门禁统一:**`can_change_activity`(发起人或持权限者)+ 状态须为 scheduled**。权限沿用现有 `CanModifyActivity` 权限类;状态校验在视图层(与 `close` / `review_submission` 同模式)。

### 1. `POST /activities/<id>/add_exhibit/` — 手动加一个展品

- multipart:`title`(选填) + `files`(一束,必传)
- 文件校验沿用 `upload_error`(全局禁用后缀 + 50MB)
- 启用投票时:为该展品建一个 `VoteOption`(text=标题);不启用则 `vote_option=NULL`
- 返回更新后的 activity detail

### 2. `PATCH /activities/<id>/update_exhibit/` — 改一个展品

- multipart:`exhibit_id` + `title`(选填)+ `files`(给了就整体覆盖旧附件)
- **改标题**:同步更新绑定的 `VoteOption.text`(启用投票时)
- **传文件**:整体覆盖——删掉该展品的旧附件(触发文件回收),建新附件
- 返回 activity detail

### 3. `DELETE /activities/<id>/delete_exhibit/` — 删一个展品

- `exhibit_id`
- 连带删:该展品的附件(文件回收)、绑定的 `VoteOption`(显式删,避免 SET_NULL 留孤儿选项)
- 返回 activity detail

### 4. `POST /activities/<id>/import_from_collection/` — 从征集复制

- JSON:`collection_id` + `submission_ids`(勾选的作品,任意 review_status)
- 对每个选中作品:
  - 建展品(**标题留空**——作品无标题字段,展品标题本就选填;策展人导入后可在详情页 `update_exhibit` 改。前端画廊对无标题展品显示「未命名」)
  - **复制文件成独立附件副本**:沿用原 `import_from_collection` 的 `ContentFile(a.file.read())` + `new_att.file.save(...)` 法,文件落到新存储路径(独立于原作品)
  - 启用投票时:每展品建一个 `VoteOption`(text 留空,与展品标题一致)
- 校验:`collection_id` 须存在且 type=collection;`submission_ids` 须属于该征集
- 返回 activity detail

## 序列化器与类型

- **后端读侧不改**:`ActivityDetailSerializer.get_exhibits` 已输出全部展品(含文件、赞踩、vote_option_id),详情页管理面板直接复用这份。
- **前端类型**:`Exhibit` 已有 `id/title/files/...`,无需新类型。
- **前端 API(`activityApi` 新增)**:
  - `addExhibit(activityId, { title, files })` → multipart POST
  - `updateExhibit(activityId, exhibitId, { title?, files? })` → multipart PATCH
  - `deleteExhibit(activityId, exhibitId)` → DELETE
  - `importFromCollection(activityId, collectionId, submissionIds[])` → POST JSON
  - (命名实现时可微调)

## 前端 UI

### 创建表单(`ActivityFormPage`)展示分支

- **删除**:展品栏(标题 / 文件录入)、「至少 1 个展品」校验、K 校验对展品数的依赖。
- **保留**:展示截止、启用投票(勾选时显示 K / 秘密——投票开关仍创建时定)。
- 提交不再带展品字段;0 展品可创建。
- 编辑模式:展示分支仍改标题 / 正文 / 时间 / 投票参数(现状不变);展品不在编辑表单管。

### 详情页(`ActivityDetailPage`)展示分支

策展人(`canManage`)+ 状态为 **scheduled(待开始)** 时,显示一块**「布展」管理面板**:

- 展品列表:每条含标题、文件名、「改」「删」按钮。
- **「+ 手动添加展品」**:展开小表单(标题 input + file 多选)→ `addExhibit`。
- **「从征集导入」**:两步——
  1. 选一个征集(下拉 / 弹窗,列 type=collection 的活动,复用现有 list 接口 `?type=collection`)
  2. 列出该征集的作品(带 review_status 徽章),勾选 → 确认 → `importFromCollection`

非策展人 / 非 scheduled 状态:不显示管理面板,只看画廊(现状不回归)。展示中 / 已结束:画廊只读。

## 边界总表

| 项 | 决定 |
|---|---|
| 创建表单展品栏 | 删除 |
| 0 展品可创建 | 是 |
| 详情页管理入口 | 手动添加 + 从征集导入(两个) |
| 可管时机 | 仅待开始(scheduled) |
| 展品操作 | 加 / 删 / 改(改 = 改标题 + 整体覆盖文件) |
| 复制范围 | 任意作品可勾选(不限录用) |
| 文件 | 复制独立副本;改展品整体覆盖 |
| 改标题与投票选项 | 同步改 VoteOption.text |
| 门禁 | `can_change_activity`(策展人 = 发起人或持权限者) |

## 测试 seam(沿用项目惯例)

- **HTTP 黑盒**(`activities/tests.py`,`ExhibitionTest` 增/改):add/update/delete/import 各动作的 happy path + 状态门禁(非 scheduled 拒绝)+ 权限门禁(非策展人 403)+ 0 展品创建;启用投票时 add/import 建选项、改标题同步选项文本;导入复制独立副本(原作品删了展品还在)。
- **lifecycle 单测**:若把「可否管展品」抽成一个 `can_manage_exhibits(activity, user)` 守卫,在 `tests_lifecycle.py` 覆盖;否则状态门禁的校验留在视图层,HTTP 测试覆盖即可。

## CONTEXT.md

展品来源描述(第 31、35 行)从「创建时录入或导入」改为「详情页布展期录入 / 编辑 / 从征集导入」,与新行为对齐。
