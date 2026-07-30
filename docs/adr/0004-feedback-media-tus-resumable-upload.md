# 署名反馈媒体上传：drf-tus 可续传 + 按大小分流的附件传输

意见反馈此前只能匿名提交纯文字。本 ADR 记录为「让反馈能附带图片 / 视频证据」所做的
一组领域与传输决策（#17 父工单，落地于 #18–#21）。

## 决策

### 1. 意见反馈拆为「署名 / 匿名」两种提交方式

- **匿名反馈**（默认；未登录只能走这条）：不记录 `creator`，**仅纯文字**。
- **署名反馈**：登录成员**主动选择**署名（`submit_feedback` 的 `disclose_identity`），
  记录 `creator`、对社长可见，**方可附带媒体**。

媒体天然携带上传者身份（`Attachment.uploaded_by`），与匿名互斥——故「附媒体」与「匿名」
不可兼得。复用现有 `is_parent_creator` 谓词授权附件上传，**零新增归属机制**。

### 2. 反馈是单向投递箱（fire-and-forget）

提交后不在系统内形成对话；跟进走线下其他渠道。故反馈的可用动作收敛为**通过 / 拒绝**（带
理由），砍掉**打回(returned)**（对定稿的反馈无意义）。反馈可见性不变（仅社长）。

### 3. 反馈上传权限 carve-out（对 ADR 0002 单一规则的特例）

ADR 0002 的「创建者 / 活跃参与者 / 管理权限」统一规则，对**反馈**做收窄：

- **上传**（`can_upload_to_parent`）：仅**署名创建者**、且仅 `pending_approval` 期间；
  持 `change_proposal` 的**社长被排除**（不上传证据到别人反馈），审结即锁死。
- **删除**（`can_manage_parent_attachments`）：沿用通用规则——社长作为反馈唯一可见者
  **能删**违规媒体（审核需要）。故社长对反馈「**能删不能传**」。

### 4. 按文件大小分流的附件传输（全系统生效）

- **≤50MB、任意类型** → 现有同步 `POST /attachments/`（**ADR 0002 保留、扩展、不废止**）。
- **>50MB、仅图片/视频、≤500MB** → **tus 可续传**端点（`POST /uploads/files/ …`）。

只有图片/视频允许超过 50MB，故「大文件」实际上只可能是图/视频；任务 / 活动申报 / 反馈
都按这一条分流。同步端点对所有类型维持 ≤50MB（同步扛不住大文件）。

### 5. tus 后端 = drf-tus（**非** django-tus）

**django-tus 已死**：2020 起未更新、classifier 仅到 Django 3.1 / Python 3.8、硬钉
`pathvalidate==2.3.0`，在 Django 6.0 / Python 3.14 上装不上也跑不了。改用 **drf-tus**
（`dirkmoors/drf-tus`，维护中、DRF 原生、显式支持 Django 3.2–6.0 / Python 3.8–3.14）：

- 自定义 `TusUpload(user)` 模型（补 `user` 外键，drf-tus 自动写入 `request.user`）。
- `TusUploadViewSet`：创建时按 `Upload-Metadata` 声明父级，校验权限（复用
  `can_upload_to_parent`，含 #3 反馈 carve-out）+ 尺寸/类型（>500MB 拒、非图/视频 >50MB 拒）
  + 反馈配额；未授权不接收字节。
- `finished` 信号钩子：把文件搬到 `attachments/<uuid>.<ext>` 并建统一 `Attachment`，
  **复核权限**（父级状态可能已变则丢弃），清理临时副本。
- **drf-tus 自身无过期清理任务**（`UPLOAD_EXPIRES` 只盖响应头）——故 `sweep_stale_tus_uploads`
  在每次创建时按 `expires` 惰性回收放弃/过期的会话（仿 `transition_overdue_proposals` 的
  自愈式清理，无需 cron）。

### 6. tus 前端 = tus-js-client（**非**完整 Uppy）

用 `tus-js-client` 而非完整的 Uppy Dashboard：更轻量，让「按大小选路」变简单，适配
「先建父级再上传」的流程；同一 tus 协议、同一 drf-tus 端点，带进度与断点续传。统一收口在
`attachmentApi.uploadRouted`（按 `MAX_SYNC_BYTES` 选路）。

## 与既有 ADR 的关系

- **ADR 0002（统一附件端点 + 单一权限规则）**：**扩展、不废止**。同步端点仍服务 ≤50MB；
  反馈上传 carve-out 是其上的特例，tus 是新增的传输通路（同一 `can_upload_to_parent`
  规则、同一 `feedback_quota_error` 配额）。
- **ADR 0003（不抽 任务/申报 共享生命周期基类）**：**无关**。反馈仍是独立状态机，仅动作集
  收敛为 通过/拒绝。

## 被否的方案

- **全量 tus 替换**（任务/申报也一并迁、删同步端点）：碰正在工作的功能、scope 大、废止
  ADR 0002，得不偿失。按大小分流让同步通路原样保留。
- **tus 只接反馈**：500MB 落不到任务/申报，违背「大小分流全系统生效」的目标。
- **自研分片协议**（非标准 tus）：续传的边角 case 多，且丢掉 tus 标准兼容与现成客户端。
- **同步传 500MB**：同步 multipart 扛不住（无进度、无续传、失败重来）——正是要 tus 的原因。
- **django-tus / 完整 Uppy**：前者死库、后者对当前流程过重（见上）。
