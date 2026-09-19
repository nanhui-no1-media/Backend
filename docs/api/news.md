# 新闻 API

门户新闻 / 公告模块：公开读（`is_published=True` 且审核通过），持 `news.manage_news` 者编写与维护；另含头条、热门阅读、标签云、社团概览与首页「社团动态」聚合端点。

> 全局约定（认证 / 错误 / 分页 / CSRF）见 [API 总览](README.md)。相关设计记录：[ADR-0005](../adr/0005-access-control-principle.md)（`has_perm` 判权）、[ADR-0009](../adr/0009-portal-review-about-tutorials.md)（统一审核轴）、[ADR-0016](../adr/0016-comment-thread-vs-dm.md)（评论区挂宿主）

挂载：`config/urls.py` 的 `news/` + app 内 router 前缀 `news`，实际路径均为 `/news/news/…`。列表类响应为 DRF 分页信封 `{count, next, previous, results}`（`PAGE_SIZE=20`）。

## 端点一览

| 方法 | 路径 | 认证 | 权限 | 说明 |
|---|---|---|---|---|
| GET | /news/news/ | 公开 | — | 新闻列表（已发布 + 已过审），分页 |
| POST | /news/news/ | 登录 | `news.manage_news` | 新建新闻，自动开审核行与评论区 |
| GET | /news/news/mine/ | 登录 | — | 作者预览：自己的全部新闻（含待审 / 驳回 / 下架） |
| GET | /news/news/{id}/ | 公开 | — | 详情；去重阅读计数；作者与审核者可预览未公开项 |
| PUT / PATCH | /news/news/{id}/ | 登录 | `news.manage_news` | 编辑（正文 / 封面 / 标签 / 头条 / 发布开关） |
| DELETE | /news/news/{id}/ | 登录 | `news.manage_news` | 删除 |
| POST | /news/news/upload_image/ | 登录 | `news.manage_news` | 正文内嵌图片上传，返回 `{url}` |
| GET | /news/news/featured/ | 公开 | — | 头条：手工置顶优先，否则阅读人数最高 |
| GET | /news/news/hot/ | 公开 | — | 热门阅读前 5 |
| GET | /news/news/tags/ | 公开 | — | 标签云（仅被公开新闻引用），带新闻数 |
| GET | /news/news/overview/ | 公开 | — | 社团概览：成员数 / 作品数 |
| GET | /news/news/feed/ | 公开 | — | 首页「社团动态」聚合（新闻 + 活动，登录另含任务） |

审核轴说明：`review_status` 取值 `pending` / `approved` / `rejected` / `removed`，无审核行时为 `null`；列表只出 `approved`，`mine` 与作者预览不受限。站点策略 `content_review_enabled` 关闭时新建即 `approved`。

## 端点详情

### 新闻列表
`GET /news/news/`

**认证**：公开；**权限**：—

**查询参数**

| 名称 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | 整数 | 否 | 页码（每页 20 条） |
| search | 字符串 | 否 | 模糊匹配 `title` / `summary` / `content` |
| ordering | 字符串 | 否 | `published_at` / `views` / `created_at`，前缀 `-` 倒序；默认 `-published_at` |
| featured | 布尔 | 否 | 仅要头条 `true` |
| is_published | 布尔 | 否 | 列表本身只出已发布，传 `false` 恒为空 |

**响应 `200 OK`**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 42,
      "title": "社团招新公告",
      "summary": "2026 学年传媒社招新安排。",
      "cover_image_url": "https://8.153.145.175/media/news_covers/6f1c9d2ab3.jpg",
      "author": {"id": 3, "username": "info", "nickname": "信息组", "avatar": "/media/avatars/1a2b.png"},
      "tags": [{"id": 1, "name": "公告", "color": "#007bff", "news_count": 2}],
      "featured": true,
      "views": 128,
      "is_published": true,
      "review_status": "approved",
      "published_at": "2026-09-12T01:00:00Z",
      "created_at": "2026-09-11T10:20:00Z"
    }
  ]
}
```

`author` 为共享的 `SimpleUserSerializer` 形状；`email` 仅本人可见（此处匿名 / 他人视角不出现）。

### 新建新闻
`POST /news/news/`

**认证**：登录；**权限**：`news.manage_news`

**请求体**（JSON 或 multipart；有封面时用 multipart）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| title | 字符串 | 是 | 上限 200 |
| summary | 字符串 | 否 | 上限 280 |
| content | 字符串 | 否 | HTML 正文，服务端经 `sanitize_html` 清洗 |
| cover_image | 文件 | 否 | jpg / png / gif / webp，≤ 2MB |
| tag_ids | 整数数组 | 否 | 复用 `tasks.Tag` |
| featured | 布尔 | 否 | 头条 |
| is_published | 布尔 | 否 | 默认 `true`；为真且无发布时间时自动补 `published_at` |

副作用：按统一审核轴创建审核行——持 `reviews.force_publish` 或站点关闭审核 → `approved`，否则 `pending`；同时自动创建该新闻的评论区。

**响应 `201 Created`**（详情序列化，见下节字段）

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | `title` 缺失 / 封面超 2MB / 封面类型不支持 |
| 403 | 无 `news.manage_news` |

### 作者预览（我的新闻）
`GET /news/news/mine/`

**认证**：登录；**权限**：—

返回当前用户的全部新闻，**不做**公开过滤（含待审 / 驳回 / 下架），支持与列表相同的 `search` / `ordering` / `featured` / `is_published` 参数。本人视角 `author.email` 保留。

**响应 `200 OK`**：与列表同形的分页信封。

### 新闻详情
`GET /news/news/{id}/`

**认证**：公开；**权限**：—

可见性：匿名与非作者登录用户只能取「已发布 + 已过审」；作者可取自己的全部条目（作者预览）；持 `reviews.moderate` 可取全部。不满足时返回 `404`。

计数：每个新读者阅读量 +1——登录按 `user:{pk}`、匿名按 `ip:{sha256(IP)}` 去重，同一读者重复打开只计一次。

**响应 `200 OK`**

```json
{
  "id": 42,
  "title": "社团招新公告",
  "summary": "2026 学年传媒社招新安排。",
  "content": "<p>报名时间：<strong>9 月 20 日</strong>。</p>",
  "cover_image_url": "https://8.153.145.175/media/news_covers/6f1c9d2ab3.jpg",
  "author": {"id": 3, "username": "info", "nickname": "信息组", "avatar": "/media/avatars/1a2b.png"},
  "tags": [{"id": 1, "name": "公告", "color": "#007bff", "news_count": 2}],
  "featured": true,
  "views": 128,
  "is_published": true,
  "review_status": "approved",
  "review_comment": "",
  "published_at": "2026-09-12T01:00:00Z",
  "related": [
    {
      "id": 41,
      "title": "校运会摄影组招募",
      "summary": "摄影志愿者报名。",
      "cover_image_url": null,
      "author": {"id": 3, "username": "info", "nickname": "信息组", "avatar": null},
      "tags": [],
      "featured": false,
      "views": 31,
      "is_published": true,
      "review_status": "approved",
      "published_at": "2026-09-05T02:00:00Z",
      "created_at": "2026-09-05T01:40:00Z"
    }
  ],
  "created_at": "2026-09-11T10:20:00Z",
  "updated_at": "2026-09-12T01:00:00Z",
  "attachments": [
    {"id": 7, "file_url": "https://8.153.145.175/media/attachments/a9c1.png",
     "file_type": "image", "file_name": "poster.png", "file_size": 204800}
  ],
  "comment_thread": {"id": 15, "status": "open", "can_manage": false}
}
```

`review_comment` 仅对待审 / 驳回条目的作者与持 `reviews.moderate` 者非空，其余人得到空串。`related` 为最新 3 条公开稿（排除自身）。`comment_thread` 的 `status` 为 `open` / `muted` / `closed`。写入用字段 `cover_image`、`tag_ids`、`comment_thread_status` 只写不出，不出现在响应中。

**错误**

| 状态码 | 场景 |
|---|---|
| 404 | 条目不存在，或对当前读者不可见 |

### 编辑新闻
`PUT /news/news/{id}/`、`PATCH /news/news/{id}/`

**认证**：登录；**权限**：`news.manage_news`（任意持权者，无按作者的对象级限制）

**请求体**：与新建相同（PUT 需含 `title`）；额外接受只写字段 `comment_thread_status`（`open` / `muted` / `closed`，由该评论区主人或协管执行，无权者 `403`）。替换封面时旧文件被删除；`is_published` 由假转真且无 `published_at` 时自动补发布时间。

**响应 `200 OK`**：详情结构（同上）。

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | 校验失败（同新建） |
| 403 | 无写权限 |
| 404 | 条目不存在 |

### 删除新闻
`DELETE /news/news/{id}/`

**认证**：登录；**权限**：`news.manage_news`

**响应 `204 No Content`**。级联回收附件、评论区与阅读记录。

### 正文内嵌图片上传
`POST /news/news/upload_image/`

**认证**：登录；**权限**：`news.manage_news`

**请求体**（multipart）：`image`（必填文件，jpg / png / gif / webp，≤ 5MB）。供富文本编辑器「插入图片」与 Word 导入内嵌图共用。

**响应 `200 OK`**

```json
{"url": "https://8.153.145.175/media/news_content_images/2b7e4f0c9a1d.png"}
```

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | 未选文件（`{"detail": "请选择图片。"}`）/ 超 5MB / 类型不支持 |

### 头条
`GET /news/news/featured/`

**认证**：公开；**权限**：—

手工置顶（`featured=true`）优先；无置顶则取阅读人数最高的一条。无任何公开新闻时返回 `null`。

**响应 `200 OK`**：单个列表项（同列表 `results` 元素）或 `null`。

### 热门阅读
`GET /news/news/hot/`

**认证**：公开；**权限**：—

按 `-views`、`-published_at` 取前 5。

**响应 `200 OK`**：列表项数组（不分页）。

### 标签云
`GET /news/news/tags/`

**认证**：公开；**权限**：—

只返回被「已发布 + 已过审」新闻引用过的标签，附该标签的新闻数。

**响应 `200 OK`**

```json
[{"id": 1, "name": "公告", "color": "#007bff", "news_count": 2}]
```

### 社团概览
`GET /news/news/overview/`

**认证**：公开；**权限**：—

**响应 `200 OK`**

```json
{"members": 86, "works": 24}
```

`members` = 活跃用户数；`works` = 已发布且已过审的新闻数。成立 / 指导 / 简介等静态行走 [关于 API](about.md) 的 `/about/overview/`。

### 社团动态聚合
`GET /news/news/feed/`

**认证**：公开；**权限**：—

**查询参数**：`limit`（整数，默认 6，钳制在 1–20）。

返回 `{featured, items}`：`featured` 为头条（同 `featured/`，且不计入 `items`）；`items` 是新闻 + 活动（登录时另含未完结任务）按时间倒序、按类型打散后的混排，活动只投影公开字段。

**响应 `200 OK`**

```json
{
  "featured": {
    "type": "news", "id": 42, "title": "社团招新公告",
    "timestamp": "2026-09-12T01:00:00+00:00",
    "summary": "2026 学年传媒社招新安排。",
    "cover_image_url": "https://8.153.145.175/media/news_covers/6f1c9d2ab3.jpg",
    "views": 128
  },
  "items": [
    {"type": "activity", "id": 8, "title": "春季影展", "timestamp": "2026-09-10T06:00:00+00:00",
     "activity_type": "exhibition", "status": "open"},
    {"type": "news", "id": 41, "title": "校运会摄影组招募", "timestamp": "2026-09-05T02:00:00+00:00",
     "summary": "摄影志愿者报名。", "cover_image_url": null, "views": 31},
    {"type": "task", "id": 17, "title": "整理器材清单", "timestamp": "2026-09-04T09:30:00+00:00",
     "status": "in_progress", "priority": "medium",
     "assignee": {"id": 4, "username": "student", "nickname": "小南", "avatar": null}}
  ]
}
```

任务项仅登录下发；访客不可见仅成员受众的调研活动。无内容时 `featured` 为 `null`、`items` 为 `[]`。
