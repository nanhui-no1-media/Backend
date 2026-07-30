# 新闻插入视频 — 设计（spec）

- 日期：2026-07-30
- 范围：让「信息组」在新闻正文（TipTap 富文本）中插入视频，支持两条路径——**外链嵌入**（B站/YouTube/腾讯/优酷）与**本地上传**（复用 tus 可续传）。
- 方案：**A —— 视频作为带记录的 `Attachment`（给 Attachment 加 news 外键），复用现有 tus 流。**

## 背景 / 现状

- 新闻正文 `News.content` 为 HTML（`TextField`），用 TipTap `RichTextEditor` 编辑，详情页以
  `dangerouslySetInnerHTML` 渲染。
- 正文经 `news/serializers.py::_sanitize_content` 用 **bleach 6.4** 清洗，白名单**不含**
  `<video>`/`<iframe>`/`<source>`；协议限 http/https/mailto/tel。
- 既有正文配图：`POST /news/upload_image/`（仅信息组，≤5MB，图片），返回 `{url}`、**无 DB 记录**。
- 大文件可续传：`attachments` app 的 tus 通路（`POST /uploads/files/`，完成钩子建统一
  `Attachment`）。`Attachment` 有 CheckConstraint 强制「task/proposal 恰一父级」；tus 仅识别
  `parent_type ∈ {task, proposal}`。
- 前端 `attachmentApi.uploadRouted`：≤50MB 同步（`POST /attachments/`，即时返回 Attachment）、
  >50MB 走 tus（完成钩子异步建附件，调用方回拉父级取 URL）。

## 决策（brainstorming 已定）

1. 同时支持「外链嵌入」+「本地上传」。
2. 上传链路：**复用 tus 可续传**（给 Attachment 加 news 父级，非新建独立端点）。
3. 嵌入信任域：**常见平台白名单**（B站/YouTube/腾讯/优酷的 embed 域），不做任意 iframe。
4. 落法 A：视频是带记录的 `Attachment`（news 外键），换 CASCADE 自动回收 + 归属 + 媒体统一。

## 架构总览

编辑器「视频」入口 → 二选一：

- **粘贴链接**：前端 `utils/videoEmbed.ts` 把视频页 URL 转成 embed iframe src → 插入自定义
  TipTap `Video` 节点（`kind:"embed"`）→ 落 `<iframe>`。
- **上传文件**：`attachmentApi.uploadRouted({parentType:"news"})` → 插入 `Video` 节点
  （`kind:"file"`）→ 落 `<video>`。

两条路径最终都变成正文 HTML 元素，详情页直接渲染；服务端清洗器是唯一安全闸门。

---

## 后端

### 数据模型 & tus 扩展（`attachments`）

- `Attachment` 新增可空外键：
  ```python
  news = models.ForeignKey("news.News", on_delete=models.CASCADE,
      null=True, blank=True, related_name="attachments", verbose_name="新闻")
  ```
- CheckConstraint 由「task/proposal 恰一」改为「task/proposal/news 恰一」+ 迁移
  （`attachments/migrations/0003_news_parent.py`，紧接现有 0001_initial / 0002_tusupload）。
- `attachments/tus.py`：
  - `_resolve_parent` 的模型表加 `"news": News`。
  - `create_attachment_from_tus` 赋值加 `news=parent if kind == "news" else None`。
  - 顶部 import `News`。
- `attachments/views.py::create`：接受 `news_id`，`parent = News.objects.get(...)`，仍走
  `can_upload_to_parent`；`Attachment.objects.create(..., news=parent if isinstance(parent, News) else None)`。
- `attachments/permissions.py`：
  ```python
  def has_parent_manage_permission(user, parent):
      if isinstance(parent, Task): return user.has_perm("tasks.manage_tasks")
      if isinstance(parent, Proposal): return user.has_perm("proposals.change_proposal")
      if isinstance(parent, News): return user.has_perm("news.change_news")
      return False
  ```
  News 媒体上传/删除 = `news.change_news`（信息组）；**无反馈式 carve-out、无状态门**
  （草稿/已发布都可加视频；改已发布本就被 viewset 的 DjangoModelPermissions 门住）。
  `can_upload_to_parent` 对 News 走 `has_parent_manage_permission`（News 无「活跃参与者」概念）。

### 清洗器（安全闸门，`news/serializers.py`）

`_NEWS_ALLOWED_TAGS` 增 `iframe`、`video`（不上 `<source>`，单源够用）。

`_NEWS_ALLOWED_ATTRS` 增：
```python
"iframe": {"src": _embed_src_allowed, "allow": [], "allowfullscreen": [],
           "frameborder": [], "width": [], "height": []},
"video": {"src": [], "controls": [], "preload": [], "width": [], "height": [], "poster": []},
```

iframe src 域名白名单（**embed 域**，不是视频页域）：
```python
_VIDEO_EMBED_HOSTS = {
    "player.bilibili.com",   # B站
    "www.youtube.com",       # YouTube（/embed/）
    "v.qq.com",              # 腾讯视频（/iframe/player.html）
    "player.youku.com",      # 优酷
}
```
用 bleach 6 的属性值回调做 host 校验（per-attribute callable：`{iframe: {src: fn}}`，
`fn(tag, name, value)` 解析 `urlparse(value).hostname`，命中集合返回 True 否则 False）。
> 实现期核对 bleach 6 callable 的精确签名/位置（tag 级 vs attr 级）；意图不变：仅可信 host 的
> iframe src 保留，其余 src 剥离使 iframe 成空壳被清掉。

`<script>`、`on*`、`javascript:` 仍被现有逻辑挡住。**服务端是真闸门**：前端绕过直发 API，
非法 iframe 也存不进。

### 序列化 & 端点（`news`）

- `NewsDetailSerializer` 加 `attachments = AttachmentSerializer(many=True, read_only=True)`
  + fields 增 `"attachments"`（供编辑器 tus 异步完成后回拉取 file_url，仿 proposals）。
- 上传**不新增端点**，复用 `POST /attachments/`（同步）与 `POST /uploads/files/`（tus）。

---

## 前端

### TipTap 视频节点（`components/rte/VideoNode.ts`，新建）

自定义 atom 节点，属性：`kind:"file"|"embed"`、`src`、`provider?`、`width?`。
- `renderHTML`：
  - file → `["video", { src, controls: "controls", preload: "metadata", ... }]`
  - embed → `["iframe", { src, frameborder:"0", allow:"autoplay; fullscreen; picture-in-picture",
    allowfullscreen:"allowfullscreen", ... }]`
- `parseHTML`：识别既有 `<video>`/`<iframe>` 回填节点（编辑已发布新闻时往返不丢）。
- 注册进 `RichTextEditor` 的 extensions 列表。

### URL→embed 转换（`utils/videoEmbed.ts`，新建）

纯函数 `parseVideoEmbed(url): {src, provider} | null`，各平台正则提 id：
- B站：`BV[0-9A-Za-z]{10}` → `https://player.bilibili.com/player.html?bvid=BV...`
- YouTube：`watch?v=` / `youtu.be/` / `embed/` → `https://www.youtube.com/embed/ID`
- 腾讯：`v.qq.com/x/cover/{c}/{vid}` 或 `/x/page/{vid}` → `https://v.qq.com/iframe/player.html?vid=VID`
- 优酷：`player.youku.com` embed 形式
- 不识别 → 返回 null（前端提示「不支持的视频链接」）。

### RichTextEditor 扩展（`components/RichTextEditor.tsx`）

沿用 `imageUpload`/`wordImport` 可选 prop 模式，新增：
- `videoUpload?: (file: File) => Promise<string>` —— 传入才显示「上传视频」。
- `videoEmbed?: boolean` —— 传入才显示「粘贴链接」。
工具栏「视频」按钮 → 小菜单（上传文件 / 粘贴链接）。粘贴链接用 `parseVideoEmbed`；
两条都 `editor.chain().focus().insertVideoNode({kind, src})`（或等价 setNode）。

### attachmentApi 扩展（`api/attachments.ts`）

`parentType` 联合加 `"news"`：
- `UploadParams` 加分支 `{ newsId: number; taskId?: undefined; proposalId?: undefined }`。
- `upload`：append `news_id`。
- `UploadLargeParams.parentType`、`uploadRouted`：把 `"news"` 映射到 `{newsId}` / tus metadata
  `parent_type:"news"`。

### 新闻表单接线 & 未保存文章（`pages/NewsFormPage.tsx`）

- `RichTextEditor` 传 `videoUpload={uploadNewsVideo}`、`videoEmbed`。
- 加 `newsIdRef`（初值取 url 的 `id`；新建模式为空）。
- `uploadNewsVideo(file)`：
  1. 若 `newsIdRef.current` 为空（新建未存）→ 先 `newsApi.create(最小草稿 FormData,
     is_published=false)` 拿 id 存入 `newsIdRef.current`（不跳转、不丢正在写的内容）。
  2. `attachmentApi.uploadRouted({parentType:"news", parentId: newsIdRef.current, file, onProgress})`。
  3. 同步（≤50MB）→ 返回的 Attachment.file_url 直接返回。
     tus（>50MB）→ 返回 void → 回拉 `newsApi.get(newsIdRef.current).attachments`，取最新一条视频的
     file_url 返回（编辑器再插入）。
- `submit`：分支由现按 `isEdit` 改为按 `newsIdRef.current`（有则 update，无则 create）。
- 失败/进度：沿用 `uploadRouted` 的 `onProgress`；表单显示进度（仿反馈表单）。

---

## 权限 / 限额

- 仅信息组（`news.change_news`）可插视频，与发稿权限一致。
- tus 上限 500MB、>50MB 必须图/视频（既有规则已含视频，无需改）。
- 反馈配额（`feedback_quota_error`）只作用于 feedback 父级，News 不涉。

## 样式

`styles/news.css`（或 detail.css）：
```css
.prose video, .prose iframe { max-width: 100%; height: auto; border-radius: var(--r-md); }
.prose .video-embed { position: relative; padding-bottom: 56.25%; height: 0; }
.prose .video-embed iframe { position: absolute; inset: 0; width: 100%; height: 100%; }
```
（iframe 16:9 容器；renderHTML 可包一层 `<div class="video-embed">`，注意该 class 已在
`*` 的 `class` 白名单内。）

## 测试

后端：
- `news/tests.py`：清洗器——可信 iframe（player.bilibili.com）保留、`evil.com` iframe 剥离、
  `<video>` 保留、`<script>` 仍挡。
- `attachments/tests.py`：Attachment 挂 news 父级 + 恰一约束（news 与 task/proposal 互斥）；
  非信息组上传 news 视频 403、信息组 200。

前端：无测试框架，`npm run build` + 手测节点往返（新建/编辑各插一次视频、详情页可见可播）。

## 不在本期（YAGNI / future）

- 抖音 / 西瓜 等平台（白名单与 parser 按需再加）。
- 未用孤儿视频文件的 GC（与现有图片同策略，暂不处理；有 Attachment 记录已使未来 GC 可行）。
- 服务端草稿自动保存（仅「首次插视频」时静默存一次取 id；不做全文服务端草稿）。
- `<source>` 多源、字幕 `<track>`、海报图自动生成。

## 风险 / 注意

- **未保存文章**：本设计用「首传静默存草稿」化解；实现时务必保证 create→拿 id→upload 的失败
  回滚与 UI 一致（草稿已建则后续按 update）。
- **bleach callable 形态**：实现期核对 6.4 的精确 API（见清洗器节注）。
- **iframe 安全**：白名单是 embed 域；勿放视频页域（www.bilibili.com 等），否则易被绕过。
- **tus 完成取 URL 的竞态**：单作者编辑下「取最新一条视频」足够；并发同传属罕见，不专门处理。
- **公开详情页的附件字段瘦身**：`NewsDetailSerializer.attachments` 复用 `AttachmentSerializer` 会带
  `uploaded_by`（SimpleUserSerializer）；新闻详情匿名可读，等于公开上传者身份。信息组身份本就半公开
  （文章已署作者），低风险；plan 期可改为只暴露 `file_url/file_type/file_name` 的精简序列化器。
