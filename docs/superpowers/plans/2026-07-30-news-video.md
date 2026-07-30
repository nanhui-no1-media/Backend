# 新闻插入视频 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「信息组」在新闻正文（TipTap 富文本）中插入视频——支持外链嵌入（B站/YouTube/腾讯/优酷）与本地上传（复用 tus 可续传），两条路径都落成正文 HTML 元素，详情页直接渲染。

**Architecture:** 方案 A。给统一 `Attachment` 加可空 `news` 外键（复用既有 tus 流与 CASCADE 回收）；`news` 清洗器放行 `<iframe>`/`<video>` 并以服务端 iframe-src 域名白名单为安全闸门；前端新增自定义 TipTap v3 `Video` 节点 + 编辑器「视频」入口；新闻表单接线 `videoUpload`/`videoEmbed`，未保存文章首次插视频时静默存服务端草稿取 id。

**Tech Stack:** Django 6 / DRF / bleach 6.4 / drf-tus（后端）；React 19 / TypeScript / TipTap v3 / tus-js-client / webpack（前端）。

**Spec:** `docs/superpowers/specs/2026-07-30-news-video-design.md`

**测试约定:** 后端走 `uv run python manage.py test <app> --keepdb`（单 app，省时）。前端无 JS 测试框架，各任务用 `npm run build`（含 tsc 类型检查）+ 末尾手动 QA 清单验证。

---

## 文件结构

**后端（创建/修改）：**
- 修改 `attachments/models.py` — `Attachment` 加 `news` 外键 + 放宽 CheckConstraint
- 新建 `attachments/migrations/0003_news_parent.py` — 迁移
- 修改 `attachments/permissions.py` — `has_parent_manage_permission` 增 News；`is_parent_creator` 容错无 creator 的父级
- 修改 `attachments/tus.py` — `_resolve_parent` + 完成钩子支持 news
- 修改 `attachments/views.py` — create 接受 `news_id`，三选一校验
- 修改 `news/serializers.py` — 清洗器放行 iframe/video + iframe src 域名白名单；`NewsAttachmentSerializer`（精简）+ `NewsDetailSerializer.attachments`
- 修改 `attachments/tests.py`、`news/tests.py` — 新增用例

**前端（创建/修改）：**
- 新建 `frontend/src/utils/videoEmbed.ts` — `parseVideoEmbed(url)`
- 新建 `frontend/src/components/rte/VideoNode.ts` — TipTap v3 Video 节点
- 修改 `frontend/src/components/RichTextEditor.tsx` — 注册 Video 节点 + `videoUpload`/`videoEmbed` prop + 工具栏入口 + 进度
- 修改 `frontend/src/api/attachments.ts` — `parentType` 增 `"news"`
- 修改 `frontend/src/types/news.ts` — `NewsAttachment` + `NewsDetail.attachments`
- 修改 `frontend/src/pages/NewsFormPage.tsx` — 接线视频上传/嵌入 + `newsIdRef` + 未保存先存草稿 + submit 分支
- 修改 `frontend/src/styles/news.css` — `.prose video`/`iframe` 响应式样式

---

## Task 1: Attachment 加 news 外键 + 恰一约束

**Files:**
- Modify: `attachments/models.py`
- Create: `attachments/migrations/0003_news_parent.py`
- Test: `attachments/tests.py`（新增 `AttachmentNewsParentTest`）

- [ ] **Step 1: 写失败测试** — 在 `attachments/tests.py` 末尾追加：

```python
# ── news 父级（#新闻视频）──
class AttachmentNewsParentTest(_AttachmentTestCase):
    """Attachment 可挂 news 父级；task/proposal/news 三选一。"""

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User
        from news.models import News
        self.user = User.objects.create_user(username="author", password="x")
        self.news = News.objects.create(title="n", author=self.user, is_published=True)
        self.task = Task.objects.create(title="t", creator=self.user, status="pending")

    def test_news_only_attachment_valid(self):
        att = Attachment(
            uploaded_by=self.user, news=self.news,
            file=upload("v.mp4", b"x", "video/mp4"),
            file_type="video", file_name="v.mp4", file_size=1,
        )
        att.full_clean()  # 不抛
        att.save()
        self.assertEqual(Attachment.objects.get(pk=att.pk).news_id, self.news.pk)

    def test_news_and_task_rejected(self):
        from django.db import IntegrityError
        att = Attachment(
            uploaded_by=self.user, news=self.news, task=self.task,
            file=upload("v.mp4", b"x", "video/mp4"),
            file_type="video", file_name="v.mp4", file_size=1,
        )
        with self.assertRaises(IntegrityError):
            att.save()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python manage.py test attachments.AttachmentNewsParentTest --keepdb`
Expected: FAIL（`Attachment()` 不接受 `news=` 关键字 / 约束仍只认 task/proposal）。

- [ ] **Step 3: 改模型** — 在 `attachments/models.py` 的 `Attachment` 类里，`proposal` 外键之后加：

```python
    news = models.ForeignKey(
        "news.News", on_delete=models.CASCADE,
        null=True, blank=True, related_name="attachments", verbose_name="新闻",
    )
```

并把 `constraints` 里的 `attachment_exactly_one_parent` 条件改为三选一：

```python
            models.CheckConstraint(
                condition=(
                    models.Q(task__isnull=False, proposal__isnull=True, news__isnull=True)
                    | models.Q(task__isnull=True, proposal__isnull=False, news__isnull=True)
                    | models.Q(task__isnull=True, proposal__isnull=True, news__isnull=False)
                ),
                name="attachment_exactly_one_parent",
                violation_error_message="附件必须且只能挂在一个父级（任务/申报/新闻）上。",
            ),
```

- [ ] **Step 4: 生成迁移**

Run: `uv run python manage.py makemigrations attachments`
Expected: 生成 `attachments/migrations/0003_news_parent.py`，含 `AddField news` + `AlterConstraint`。打开核对这两项都在。

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run python manage.py test attachments.AttachmentNewsParentTest --keepdb`
Expected: PASS（2 个用例）。

- [ ] **Step 6: 回归既有附件测试**

Run: `uv run python manage.py test attachments --keepdb`
Expected: 全绿（新增 2 个 + 原有用例不受影响）。

- [ ] **Step 7: 提交**

```bash
git add attachments/models.py attachments/migrations/0003_news_parent.py attachments/tests.py
git commit -m "feat(attachments): Attachment 支持 news 父级（恰一约束放宽为三选一）"
```

---

## Task 2: news 清洗器放行 iframe/video + iframe src 域名白名单

**Files:**
- Modify: `news/serializers.py`
- Test: `news/tests.py`（新增 `SanitizeVideoTest`）

> 说明：iframe src 用 bleach 6 的 **tag 级属性回调** 做域名校验——对 `iframe` 的每个属性调用
> `_iframe_src_filter(tag, name, value)`：`src` 仅可信 embed host 放行，其余属性只保留一个安全白名单
> （`allow`/`frameborder`/`width`/`height`/`loading`），`on*`/`style` 等一律剥离。

- [ ] **Step 1: 写失败测试** — 在 `news/tests.py` 顶部确保有 `from django.test import TestCase`，然后追加：

```python
class SanitizeVideoTest(TestCase):
    """正文清洗器对视频元素的安全闸门。"""

    def _clean(self, html):
        from news.serializers import _sanitize_content
        return _sanitize_content(html)

    def test_keeps_bilibili_iframe(self):
        html = '<iframe src="https://player.bilibili.com/player.html?bvid=BV1xx911x7x"></iframe>'
        out = self._clean(html)
        self.assertIn("player.bilibili.com", out)
        self.assertIn("<iframe", out)

    def test_strips_unknown_iframe_host(self):
        out = self._clean('<iframe src="https://evil.com/player.html"></iframe>')
        self.assertNotIn("evil.com", out)
        self.assertNotIn("<iframe", out)

    def test_strips_iframe_event_handler(self):
        out = self._clean(
            '<iframe src="https://player.bilibili.com/player.html?bvid=BV1xx911x7x" onload="alert(1)"></iframe>'
        )
        self.assertIn("player.bilibili.com", out)
        self.assertNotIn("onload", out)

    def test_keeps_video_tag(self):
        out = self._clean('<video src="https://cdn.example.com/x.mp4" controls></video>')
        self.assertIn("<video", out)
        self.assertIn("controls", out)
        self.assertIn("cdn.example.com/x.mp4", out)

    def test_strips_script(self):
        out = self._clean('<video src="https://cdn.example.com/x.mp4"></video><script>alert(1)</script>')
        self.assertNotIn("<script", out)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python manage.py test news.SanitizeVideoTest --keepdb`
Expected: FAIL（iframe/video 被 bleach 全剥离）。

- [ ] **Step 3: 改清洗器** — 在 `news/serializers.py` 顶部加 `import urllib.parse`，然后：

在 `_NEWS_ALLOWED_PROTOCOLS` 之后加常量与回调：

```python
# 视频外链嵌入：仅信任常见平台的 embed 域（非视频页域），其余 iframe src 一律剥离。
_VIDEO_EMBED_HOSTS = frozenset({
    "player.bilibili.com",   # B站
    "www.youtube.com",       # YouTube（/embed/）
    "v.qq.com",              # 腾讯视频（/iframe/player.html）
    "player.youku.com",      # 优酷
})
_IFRAME_SAFE_ATTRS = frozenset({"allow", "frameborder", "width", "height", "loading"})


def _iframe_src_filter(tag, name, value):
    """bleach 属性回调：iframe 的 src 仅可信 embed 域放行，其余属性走安全白名单。"""
    if name == "src":
        try:
            host = urllib.parse.urlparse(value).hostname
        except (ValueError, TypeError):
            return False
        return host in _VIDEO_EMBED_HOSTS
    return name in _IFRAME_SAFE_ATTRS
```

`_NEWS_ALLOWED_TAGS` 追加 `"iframe"`, `"video"`：

```python
    "a", "img",
    "iframe", "video",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
```

`_NEWS_ALLOWED_ATTRS` 追加两行：

```python
    "img": ["src", "alt", "title", "width", "height"],
    "iframe": _iframe_src_filter,
    "video": ["src", "controls", "preload", "width", "height", "poster"],
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python manage.py test news.SanitizeVideoTest --keepdb`
Expected: PASS（5 个用例）。

- [ ] **Step 5: 回归 news 测试**

Run: `uv run python manage.py test news --keepdb`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add news/serializers.py news/tests.py
git commit -m "feat(news): 清洗器放行 iframe/video + iframe src 域名白名单"
```

---

## Task 3: 附件权限支持 News 父级

**Files:**
- Modify: `attachments/permissions.py`
- Test: `attachments/tests.py`（新增 `UploadNewsPermissionTest`）

- [ ] **Step 1: 写失败测试** — 在 `attachments/tests.py` 追加（顶部已 import `Group, User`、`News` 用局部导入）：

```python
# ── news 父级上传权限（#新闻视频）──
class UploadNewsPermissionTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import Permission
        from news.models import News
        self.author = User.objects.create_user(username="author", password="x")
        self.author.user_permissions.add(Permission.objects.get(codename="change_news"))
        self.outsider = User.objects.create_user(username="outsider", password="x")
        self.news = News.objects.create(title="n", author=self.author, is_published=True)
        self.client = APIClient()

    def _post(self, user):
        self.client.force_authenticate(user)  # pyright: ignore[reportAttributeAccessIssue]
        return self.client.post(
            "/attachments/", {"file": upload("v.mp4", b"x", "video/mp4"), "news_id": self.news.pk},
            format="multipart",
        )

    def test_news_author_can_upload(self):
        self.assertEqual(self._post(self.author).status_code, 201)

    def test_outsider_cannot_upload_to_news(self):
        self.assertEqual(self._post(self.outsider).status_code, 403)
```

> 注：此测试依赖 Task 4（views 接受 `news_id`）与 Task 1（模型）。先写测试（红），Task 4 实装后转绿——
> 本任务只先把权限层改好，views 在 Task 4 接通。本任务结束时该测试仍可能因 `news_id` 未被识别而 400；
> 故本任务的步骤 5 只跑权限**单元**断言（见下），HTTP 用例留给 Task 4 收口。

- [ ] **Step 2: 改权限** — `attachments/permissions.py`：

顶部 import 加 News：

```python
from news.models import News
from proposals.models import Proposal
from tasks.lifecycle import is_active_participant
from tasks.models import Task
```

`is_parent_creator` 改为容错（News 无 `creator`，只有 `author`）：

```python
def is_parent_creator(user, parent):
    """父级创建者（任务/申报的 creator）。News 用 author 维度，此处对无 creator 的父级返回 False。"""
    creator_id = getattr(parent, "creator_id", None)
    return creator_id is not None and creator_id == user.pk
```

`has_parent_manage_permission` 加 News 分支：

```python
def has_parent_manage_permission(user, parent):
    """父级管理权限：任务 = tasks.manage_tasks；申报 = proposals.change_proposal；新闻 = news.change_news。"""
    if isinstance(parent, Task):
        return user.has_perm("tasks.manage_tasks")
    if isinstance(parent, Proposal):
        return user.has_perm("proposals.change_proposal")
    if isinstance(parent, News):
        return user.has_perm("news.change_news")
    return False
```

（`can_upload_to_parent` 无需改：News 非 feedback Proposal，落到 `can_manage_parent_attachments`，经由上面新增的 News 分支判定 `news.change_news`。）

- [ ] **Step 3: 单元验证权限函数** — 临时核对（不必入库）：

Run:
```bash
uv run python manage.py shell -c "from django.test import Client; print('ok')"
```
Expected: `ok`（仅确认 import 无环；真实断言在 Task 4 的 HTTP 用例）。更稳妥：直接在 Task 4 跑 `UploadNewsPermissionTest`。

- [ ] **Step 4: 确认无 import 循环**

Run: `uv run python manage.py check`
Expected: 无错误（`news.models` 不依赖 `attachments`，无环）。

- [ ] **Step 5: 暂不单独提交** — 与 Task 4 一并提交（权限+views 共同接通 news 上传）。

---

## Task 4: tus + views 接受 news 父级

**Files:**
- Modify: `attachments/tus.py`
- Modify: `attachments/views.py`
- Test: `attachments/tests.py`（Task 3 的 `UploadNewsPermissionTest` 转绿 + 新增 tus news 用例）

- [ ] **Step 1: 写失败测试** — 在 `attachments/tests.py` 的 `TusUploadTest` 类里追加两法（复用其 `_create`/`_patch`）：

```python
    def test_tus_upload_to_news_creates_attachment(self):  # 新闻视频父级路径
        from news.models import News
        news = News.objects.create(title="n", author=self.creator, is_published=True)
        chunk = b"news-video-bytes"
        resp = self._create(
            self.creator, length=len(chunk), filetype="video/mp4", filename="v.mp4",
            parent_type="news", parent_id=news.pk,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(self._patch(resp.get("Location") or resp["Location"], chunk).status_code, 204)  # type: ignore[attr-defined]
        att = Attachment.objects.get(news=news)
        self.assertEqual(att.uploaded_by, self.creator)
        self.assertEqual(att.file_type, "video")
```

> `self.creator` 在 `TusUploadTest.setUp` 已建；但它无 `news.change_news` 权限，tus 创建会 403。
> 故步骤 1 之前需在 `TusUploadTest.setUp` 给 creator 加权限：

```python
        from django.contrib.auth.models import Permission
        self.creator.user_permissions.add(Permission.objects.get(codename="change_news"))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python manage.py test attachments.UploadNewsPermissionTest attachments.TusUploadTest.test_tus_upload_to_news_creates_attachment --keepdb`
Expected: FAIL（`_resolve_parent` 不认 `news` → tus 400；views 不认 `news_id` → 400）。

- [ ] **Step 3: 改 tus** — `attachments/tus.py`：

顶部 import 加：

```python
from news.models import News
```

`_resolve_parent` 的模型表加 news：

```python
    model = {"task": Task, "proposal": Proposal, "news": News}.get(ptype)
```

`create_attachment_from_tus` 的 `Attachment(...)` 构造加 news 字段：

```python
    attachment = Attachment(
        uploaded_by=user,
        task=parent if kind == "task" else None,
        proposal=parent if kind == "proposal" else None,
        news=parent if kind == "news" else None,
        file_type=file_type,
        file_name=filename,
        file_size=instance.upload_length,
    )
```

- [ ] **Step 4: 改 views** — `attachments/views.py` 的 `create`，把父级解析改为三选一：

```python
        task_id = request.data.get("task_id")
        proposal_id = request.data.get("proposal_id")
        news_id = request.data.get("news_id")
        candidates = [
            ("task", task_id, Task),
            ("proposal", proposal_id, Proposal),
            ("news", news_id, News),
        ]
        specified = [(kind, pid, model) for (kind, pid, model) in candidates if pid not in (None, "")]
        if len(specified) != 1:
            return Response(
                {"detail": "必须且只能指定一个父级（task_id / proposal_id / news_id）"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        kind, pid, parent_model = specified[0]
        try:
            parent = parent_model.objects.get(pk=pid)
        except (parent_model.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "指定的父级不存在"}, status=status.HTTP_404_NOT_FOUND,
            )
```

并把 `Attachment.objects.create(...)` 的父级赋值改为按 kind：

```python
        attachment = Attachment.objects.create(
            uploaded_by=request.user,
            task=parent if isinstance(parent, Task) else None,
            proposal=parent if isinstance(parent, Proposal) else None,
            news=parent if isinstance(parent, News) else None,
            file=file,
            file_type=file_type,
            file_name=file.name,
            file_size=file.size,
        )
```

`attachments/views.py` 顶部 import 加：

```python
from news.models import News
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run python manage.py test attachments.UploadNewsPermissionTest attachments.TusUploadTest --keepdb`
Expected: PASS（含新 news 用例）。

- [ ] **Step 6: 回归全部 attachments 测试**

Run: `uv run python manage.py test attachments --keepdb`
Expected: 全绿。

- [ ] **Step 7: 提交**（含 Task 3 的权限改动）

```bash
git add attachments/permissions.py attachments/tus.py attachments/views.py attachments/tests.py
git commit -m "feat(attachments): 权限/tus/views 接通 news 父级上传"
```

---

## Task 5: NewsDetailSerializer 暴露精简 attachments

**Files:**
- Modify: `news/serializers.py`
- Test: `attachments/tests.py`（新增 `NewsDetailAttachmentsTest`，复用 `_AttachmentTestCase`）

> 公开详情页匿名可读，故用精简 `NewsAttachmentSerializer`：只暴露 `id/file_url/file_type/file_name/file_size`，
> **不含** `uploaded_by`（避免公开上传者身份）。复用 `AttachmentSerializer.get_file_url`（需 request context）。

- [ ] **Step 1: 写失败测试** — 在 `attachments/tests.py` 追加：

```python
# ── 新闻详情内联视频附件（精简、不含 uploaded_by）──
class NewsDetailAttachmentsTest(_AttachmentTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import Permission
        from news.models import News
        self.author = User.objects.create_user(username="author", password="x")
        self.author.user_permissions.add(Permission.objects.get(codename="change_news"))
        self.news = News.objects.create(title="n", author=self.author, is_published=True)
        self.client = APIClient()
        self.client.force_authenticate(self.author)
        resp = self.client.post(
            "/attachments/",
            {"file": upload("v.mp4", b"x", "video/mp4"), "news_id": self.news.pk},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201)

    def test_news_detail_inlines_attachments(self):
        resp = self.client.get(f"/news/news/{self.news.pk}/")
        self.assertEqual(resp.status_code, 200)
        atts = resp.data["attachments"]  # pyright: ignore[reportAttributeAccessIssue]
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["file_type"], "video")
        self.assertIn("file_url", atts[0])
        self.assertNotIn("uploaded_by", atts[0])
```

> 路由前缀按现有 `config/urls.py`：news app 挂在 `/news/`，viewset 路由为 `/news/news/`。若实测 404，
> 先 `uv run python manage.py show_urls | grep news` 确认确切路径后改测试 URL。

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python manage.py test attachments.NewsDetailAttachmentsTest --keepdb`
Expected: FAIL（`attachments` 字段不存在 → KeyError）。

- [ ] **Step 3: 改序列化器** — `news/serializers.py`：

顶部 import 加：

```python
from attachments.serializers import AttachmentSerializer
```

在 `NewsDetailSerializer` 之前加精简序列化器：

```python
class NewsAttachmentSerializer(AttachmentSerializer):
    """新闻详情用的精简附件视图：不含 uploaded_by（详情匿名可读）。复用父类 get_file_url。"""

    class Meta:
        model = Attachment
        fields = ["id", "file_url", "file_type", "file_name", "file_size"]
```

> `Attachment` 需在 `news/serializers.py` 可见——顶部加 `from attachments.models import Attachment`。

`NewsDetailSerializer` 类体加字段 + import：

```python
class NewsDetailSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    reviewed_by = SimpleUserSerializer(read_only=True)
    votes = VoteSerializer(many=True, read_only=True)
    attachments = NewsAttachmentSerializer(many=True, read_only=True)
    my_vote = serializers.SerializerMethodField()
```

`fields` 列表里加 `"attachments"`（放在 `"votes", "my_vote", "attachments",` 一行，或单独加）。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python manage.py test attachments.NewsDetailAttachmentsTest --keepdb`
Expected: PASS。

- [ ] **Step 5: 回归 news + attachments**

Run: `uv run python manage.py test news attachments --keepdb`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add news/serializers.py attachments/tests.py
git commit -m "feat(news): 详情暴露精简 attachments（视频附件，不含上传者）"
```

---

## Task 6: 前端类型 — NewsAttachment + NewsDetail.attachments

**Files:**
- Modify: `frontend/src/types/news.ts`

- [ ] **Step 1: 加类型** — 在 `frontend/src/types/news.ts` 的 `NewsTag` 之后加：

```ts
export interface NewsAttachment {
  id: number;
  file_url: string;
  file_type: "image" | "video" | "document" | "archive" | "other";
  file_name: string;
  file_size: number;
}
```

`NewsDetail` 接口加 `attachments`：

```ts
export interface NewsDetail extends NewsListItem {
  content: string;
  related: NewsListItem[];
  attachments: NewsAttachment[];
  updated_at: string;
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run build`
Expected: 编译通过（无 TS 错）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/types/news.ts
git commit -m "feat(news): 前端 NewsAttachment 类型 + 详情 attachments"
```

---

## Task 7: attachmentApi 支持 parentType "news"

**Files:**
- Modify: `frontend/src/api/attachments.ts`

- [ ] **Step 1: 扩联合类型与映射** — `frontend/src/api/attachments.ts`：

`UploadParams` 加 news 分支：

```ts
type UploadParams = { file: File } & (
  | { taskId: number; proposalId?: undefined; newsId?: undefined }
  | { proposalId: number; taskId?: undefined; newsId?: undefined }
  | { newsId: number; taskId?: undefined; proposalId?: undefined }
);
```

`upload` 追加 `news_id`：

```ts
  upload: (params: UploadParams): Promise<Attachment> => {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.taskId != null) formData.append("task_id", String(params.taskId));
    if (params.proposalId != null) formData.append("proposal_id", String(params.proposalId));
    if (params.newsId != null) formData.append("news_id", String(params.newsId));
    return request("/", { method: "POST", body: formData });
  },
```

`UploadLargeParams.parentType` 与 `uploadRouted` 的 `parentType` 都加 `"news"`：

```ts
type UploadLargeParams = {
  file: File;
  parentType: "task" | "proposal" | "news";
  parentId: number;
  onProgress?: (ratio: number) => void;
};
```

`uploadRouted` 的同步分支加 news：

```ts
  uploadRouted: (params: {
    parentType: "task" | "proposal" | "news";
    parentId: number;
    file: File;
    onProgress?: (ratio: number) => void;
  }): Promise<Attachment | void> => {
    if (params.file.size <= MAX_SYNC_BYTES) {
      return attachmentApi.upload(
        params.parentType === "task"
          ? { taskId: params.parentId, file: params.file }
          : params.parentType === "proposal"
            ? { proposalId: params.parentId, file: params.file }
            : { newsId: params.parentId, file: params.file },
      );
    }
    return attachmentApi.uploadLarge({
      parentType: params.parentType,
      parentId: params.parentId,
      file: params.file,
      onProgress: params.onProgress,
    });
  },
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run build`
Expected: 编译通过。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/attachments.ts
git commit -m "feat(api): attachmentApi 支持 parentType news"
```

---

## Task 8: URL→embed 转换工具 parseVideoEmbed

**Files:**
- Create: `frontend/src/utils/videoEmbed.ts`

- [ ] **Step 1: 新建文件** — `frontend/src/utils/videoEmbed.ts`：

```ts
/**
 * 把常见视频平台的「视频页 URL」转成可嵌入的 iframe player src。
 * 服务端清洗器另以 iframe src 域名白名单兜底（见 news/serializers.py），故此处仅做转换、不做安全。
 * 不识别的链接返回 null（调用方提示「不支持的视频链接」）。
 */
export function parseVideoEmbed(
  url: string,
): { src: string; provider: "bilibili" | "youtube" | "qq" | "youku" } | null {
  const u = (url || "").trim();
  if (!u) return null;

  // B站：bilibili.com/video/BVxxxxxxxxxx
  const bv = u.match(/bilibili\.com\/video\/(BV[0-9A-Za-z]{10})/);
  if (bv) return { src: `https://player.bilibili.com/player.html?bvid=${bv[1]}`, provider: "bilibili" };

  // YouTube：watch?v= / embed/ / shorts/ / youtu.be/
  const yt = u.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/);
  if (yt) return { src: `https://www.youtube.com/embed/${yt[1]}`, provider: "youtube" };

  // 腾讯视频：x/cover/<cover>/<vid>.html 或 x/page/<vid>.html
  const qq = u.match(/v\.qq\.com\/x\/(?:cover\/[\w]+\/([\w]+)|page\/([\w]+))\.html/);
  if (qq) {
    const vid = qq[1] || qq[2];
    return { src: `https://v.qq.com/iframe/player.html?vid=${vid}&tiny=0&auto=0`, provider: "qq" };
  }

  // 优酷：v_show/id_<id>.html
  const yk = u.match(/youku\.com\/v_show\/id_([\w=]+)\.html/);
  if (yk) return { src: `https://player.youku.com/embed/${yk[1]}`, provider: "youku" };

  return null;
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run build`
Expected: 编译通过。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/utils/videoEmbed.ts
git commit -m "feat(news): parseVideoEmbed 工具（B站/YouTube/腾讯/优酷 → embed src）"
```

---

## Task 9: TipTap v3 Video 节点

**Files:**
- Create: `frontend/src/components/rte/VideoNode.ts`

- [ ] **Step 1: 新建文件** — `frontend/src/components/rte/VideoNode.ts`：

```ts
import { Node, mergeAttributes } from "@tiptap/core";

type VideoAttrs = {
  kind: "file" | "embed";
  src: string;
  provider: "bilibili" | "youtube" | "qq" | "youku" | null;
};

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    video: {
      /** 在光标处插入一个视频节点（本地上传 file / 外链嵌入 embed）。 */
      insertVideo: (attrs: VideoAttrs) => ReturnType;
    };
  }
}

/**
 * 视频原子节点：
 * - file → 渲染 <video src controls preload="metadata">（本地上传）
 * - embed → 渲染 <iframe src frameborder allow>（外链嵌入，16:9 由 CSS 给）
 * renderHTML 手控输出（不经 HTMLAttributes 自动渲染），故内部 kind/provider 不会漏成 HTML 属性。
 */
export const Video = Node.create({
  name: "video",
  group: "block",
  atom: true,

  addAttributes() {
    return {
      kind: { default: "file" },
      src: { default: "" },
      provider: { default: null },
    };
  },

  parseHTML() {
    return [
      {
        tag: "video",
        getAttrs: (el) => ({ kind: "file", src: (el as HTMLElement).getAttribute("src") || "" }),
      },
      {
        tag: "iframe",
        getAttrs: (el) => ({ kind: "embed", src: (el as HTMLElement).getAttribute("src") || "" }),
      },
    ];
  },

  renderHTML({ node }) {
    const src = String(node.attrs.src ?? "");
    if (node.attrs.kind === "embed") {
      return [
        "iframe",
        mergeAttributes({
          src,
          frameborder: "0",
          allow: "autoplay; fullscreen; picture-in-picture",
        }),
      ];
    }
    return ["video", mergeAttributes({ src, controls: "controls", preload: "metadata" })];
  },

  addCommands() {
    return {
      insertVideo:
        (attrs) =>
        ({ commands }) =>
          commands.insertContent({ type: "video", attrs }),
    };
  },
});
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run build`
Expected: 编译通过（节点尚未注册，仅类型/语法检查）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/rte/VideoNode.ts
git commit -m "feat(news): TipTap v3 Video 节点（file→video / embed→iframe）"
```

---

## Task 10: RichTextEditor 注册 Video + 视频入口

**Files:**
- Modify: `frontend/src/components/RichTextEditor.tsx`

- [ ] **Step 1: 加 import** — 顶部加：

```ts
import { Video } from "./rte/VideoNode";
import { parseVideoEmbed } from "../utils/videoEmbed";
```

`Props` 接口加两个可选 prop：

```ts
  /** 视频上传：传入即启用「上传视频」按钮；返回上传后的视频 URL（可带进度）。 */
  videoUpload?: (file: File, onProgress: (ratio: number) => void) => Promise<string>;
  /** 启用「嵌入视频链接」按钮（外链转 embed）。 */
  videoEmbed?: boolean;
```

- [ ] **Step 2: 注册节点** — `useEditor` 的 `extensions` 数组里，`TiptapImage.configure(...)` 之后加：

```ts
      TiptapImage.configure({ inline: true }),
      Video,
      Placeholder.configure({ placeholder }),
```

- [ ] **Step 3: 组件内加上传状态与处理** — 在 `RichTextEditor` 函数体内（`wordInput` ref 之后）加：

```ts
  const videoInput = useRef<HTMLInputElement>(null);
  const [videoProgress, setVideoProgress] = useState<number | null>(null);
```

并在 `importWord` 函数之后加：

```ts
  const insertVideoFile = async (file: File | null) => {
    if (!file || !editor || !videoUpload) return;
    setErr("");
    setVideoProgress(null);
    try {
      const src = await videoUpload(file, setVideoProgress);
      editor.chain().focus().insertVideo({ kind: "file", src, provider: null }).run();
    } catch (e: any) {
      setErr(e?.message || "视频上传失败");
    } finally {
      setVideoProgress(null);
    }
  };

  const insertVideoEmbed = () => {
    if (!editor) return;
    const url = window.prompt("粘贴视频链接（B站 / YouTube / 腾讯 / 优酷）", "https://");
    if (url === null) return;
    const parsed = parseVideoEmbed(url);
    if (!parsed) {
      setErr("不支持的视频链接，请粘贴 B站 / YouTube / 腾讯 / 优酷 的视频页地址");
      return;
    }
    setErr("");
    editor.chain().focus().insertVideo({ kind: "embed", src: parsed.src, provider: parsed.provider }).run();
  };
```

- [ ] **Step 4: 工具栏加按钮** — `Icon` 对象加一个视频图标：

```ts
const Icon = {
  // …既有 image / link / doc…
  video: (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="14" height="14" rx="2" /><path d="M17 9l4-2v10l-4-2" />
    </svg>
  ),
};
```

`Toolbar` 组件的 props 加 `videoUpload`、`videoEmbed`、`onInsertVideoFile`、`onInsertVideoEmbed`：

```ts
const Toolbar = ({
  editor, imageUpload, wordImport, importing,
  onInsertImage, onAddLink, onImportWord,
  videoUpload, videoEmbed, onInsertVideoFile, onInsertVideoEmbed,
}: {
  editor: ReturnType<typeof useEditor>;
  imageUpload?: Props["imageUpload"];
  wordImport?: boolean;
  importing: boolean;
  onInsertImage: () => void;
  onAddLink: () => void;
  onImportWord: () => void;
  videoUpload?: Props["videoUpload"];
  videoEmbed?: boolean;
  onInsertVideoFile: () => void;
  onInsertVideoEmbed: () => void;
}) => {
```

`rte-actions` 那组里，`wordImport` 按钮之后加：

```tsx
        {videoEmbed && (
          <button type="button" className="rte-action" onClick={onInsertVideoEmbed} title="嵌入视频链接（B站/YouTube/腾讯/优酷）">
            {Icon.video} 嵌入视频
          </button>
        )}
        {videoUpload && (
          <button type="button" className="rte-action" onClick={onInsertVideoFile} title="上传视频文件">
            {Icon.video} 上传视频
          </button>
        )}
```

`{(imageUpload || wordImport) && <span className="rte-spacer" />}` 的条件改为 `{(imageUpload || wordImport || videoUpload || videoEmbed) && <span className="rte-spacer" />}`。

- [ ] **Step 5: 传 props + 渲染进度 + 隐藏 input** — 主组件 return 里，`<Toolbar ... />` 调用加：

```tsx
        videoUpload={videoUpload}
        videoEmbed={videoEmbed}
        onInsertVideoFile={() => videoInput.current?.click()}
        onInsertVideoEmbed={insertVideoEmbed}
```

在 `{err && ...}` 之后加进度条：

```tsx
      {videoProgress != null && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "6px 0" }}>
          <span>视频上传 {Math.round(videoProgress * 100)}%</span>
          <div style={{ flex: 1, height: 6, background: "#e5e7eb", borderRadius: 4, overflow: "hidden" }}>
            <div style={{ width: `${Math.round(videoProgress * 100)}%`, height: "100%", background: "#2563eb", transition: "width .2s" }} />
          </div>
        </div>
      )}
```

在底部 `<input ref={wordInput} .../>` 之后加隐藏的视频文件选择：

```tsx
      <input
        ref={videoInput} type="file" accept="video/*" className="rte-file"
        onChange={(e) => { insertVideoFile(e.target.files?.[0] ?? null); e.target.value = ""; }}
      />
```

并把 `videoUpload`、`videoEmbed` 加入 `RichTextEditor` 的解构参数。

- [ ] **Step 6: 类型检查**

Run: `cd frontend && npm run build`
Expected: 编译通过。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/RichTextEditor.tsx
git commit -m "feat(news): 富文本编辑器加视频入口（嵌入 + 上传 + 进度）"
```

---

## Task 11: NewsFormPage 接线视频上传/嵌入 + 未保存先存草稿

**Files:**
- Modify: `frontend/src/pages/NewsFormPage.tsx`

- [ ] **Step 1: 加 import** — 顶部加：

```ts
import { attachmentApi } from "../api/attachments";
```

- [ ] **Step 2: 加 newsIdRef + 视频上传回调** — 在 `const fileRef = ...` 附近加：

```ts
  const newsIdRef = useRef<number | null>(id ? Number(id) : null);
```

在 `discardDraft` 之后、`submit` 之前加：

```ts
  const uploadNewsVideo = async (file: File, onProgress: (ratio: number) => void): Promise<string> => {
    // 新建且尚未保存：先存一份服务端草稿拿到 id（tus/Attachment 必须挂已存在的 news_id）
    if (!newsIdRef.current) {
      const draftFd = new FormData();
      draftFd.append("title", title.trim() || "未命名草稿");
      draftFd.append("category", category);
      draftFd.append("content", content);
      draftFd.append("summary", summary);
      draftFd.append("is_published", "false");
      const draft = await newsApi.create(draftFd);
      newsIdRef.current = draft.id;
      setDraftRestored(false);  // 草稿已在服务端，本地草稿不再相关
    }
    const att = await attachmentApi.uploadRouted({
      parentType: "news", parentId: newsIdRef.current, file, onProgress,
    });
    if (att && att.file_url) return att.file_url;
    // tus（>50MB）异步完成：回拉详情，取最新一条视频附件的 URL
    const fresh = await newsApi.get(newsIdRef.current);
    const latest = (fresh.attachments || []).find((a) => a.file_type === "video");
    if (!latest) throw new Error("视频处理中，请稍后重试");
    return latest.file_url;
  };
```

- [ ] **Step 3: submit 按 newsIdRef 决定 create/update** — `submit` 里把：

```ts
      const saved = isEdit ? await newsApi.update(Number(id), fd) : await newsApi.create(fd);
```

改为：

```ts
      const saved = newsIdRef.current
        ? await newsApi.update(newsIdRef.current, fd)
        : await newsApi.create(fd);
      if (!newsIdRef.current) newsIdRef.current = saved.id;
```

- [ ] **Step 4: 给 RichTextEditor 传视频 prop** — `<RichTextEditor .../>` 加：

```tsx
            videoUpload={uploadNewsVideo}
            videoEmbed
```

- [ ] **Step 5: 类型检查**

Run: `cd frontend && npm run build`
Expected: 编译通过。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/NewsFormPage.tsx
git commit -m "feat(news): 撰写页接线视频上传/嵌入；未保存文章首传静默存草稿取 id"
```

---

## Task 12: 正文视频响应式样式

**Files:**
- Modify: `frontend/src/styles/news.css`

- [ ] **Step 1: 加样式** — 在 `frontend/src/styles/news.css` 末尾加：

```css
/* 正文内嵌视频 / 外链播放器：响应式、圆角；iframe 用 aspect-ratio 维持 16:9（无需包裹 div，避免 bleach 剥离 div） */
.prose video,
.prose iframe {
  max-width: 100%;
  height: auto;
  border-radius: var(--r-md);
  display: block;
  margin: var(--s-4) auto;
}
.prose iframe {
  width: 100%;
  aspect-ratio: 16 / 9;
}
```

- [ ] **Step 2: 构建**

Run: `cd frontend && npm run build`
Expected: 编译通过。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/styles/news.css
git commit -m "style(news): 正文 video/iframe 响应式（16:9）样式"
```

---

## Task 13: 全量回归 + 手动 QA

**Files:** 无（验证）

- [ ] **Step 1: 后端全量回归**

Run: `uv run python manage.py test news attachments --keepdb`
Expected: 全绿。

- [ ] **Step 2: Django check**

Run: `uv run python manage.py check`
Expected: no issues。

- [ ] **Step 3: 前端构建**

Run: `cd frontend && npm run build`
Expected: 编译通过（既有体积 warning 无妨）。

- [ ] **Step 4: 手动 QA（起服务：`uv run python manage.py runserver` + 另起 `cd frontend && npm run dev`）**

以信息组账号登录，`/news/new`：
1. **嵌入**：点「嵌入视频」→ 粘贴一个 B站视频页 URL → 正文出现 iframe；保存后详情页可见可播。
2. **上传（小文件）**：点「上传视频」→ 选一个 ≤50MB 的 mp4 → 进度条走完，正文出现 `<video>`；详情页可播。
3. **未保存先存草稿**：新建状态（URL 仍是 `/news/new`）直接上传视频 → 应静默存草稿（不报错、不跳转）；继续编辑后点「发布」→ 走 update，视频仍在。
4. **安全**：尝试嵌入一个 `https://evil.com` 链接 → 编辑器提示「不支持」；即便手工绕过直发 API，详情页该 iframe 被剥（服务端白名单兜底）。
5. **大文件（可选）**：>50MB 视频走 tus，进度条续传，完成后正文出现 `<video>`。

- [ ] **Step 5: 收尾提交（若有 QA 中发现的小修）**

```bash
git add -A
git commit -m "fix(news): 视频插入 QA 收尾"
```

---

## Self-Review（写完后自检，已修正）

- **Spec 覆盖**：① Attachment news 外键 → Task 1；② tus/权限/views 接通 → Task 3/4；③ 清洗器 iframe/video + 域名白名单 → Task 2；④ NewsDetailSerializer attachments（精简）→ Task 5；⑤ TipTap Video 节点 → Task 9；⑥ 编辑器入口 → Task 10；⑦ 表单接线 + 未保存草稿 → Task 11；⑧ 样式 → Task 12。spec 各节均有对应任务。
- **占位符**：无 TBD/TODO；每步含完整代码或确切命令。
- **类型一致**：`parseVideoEmbed` 返回 `{src, provider}` 的 `provider` 取值（`"bilibili"|"youtube"|"qq"|"youku"`）与 `VideoNode` 的 `VideoAttrs.provider` 一致；`insertVideo({kind, src, provider})` 在编辑器两处调用与节点 `addCommands` 签名一致；`attachmentApi.uploadRouted({parentType:"news",...})` 与 Task 7 扩展一致。
- **与 spec 的偏差（已记录）**：spec 写了 `.video-embed` 包裹 div，但 `div` 不在清洗器白名单 → plan 改为裸 iframe + CSS `aspect-ratio:16/9`（Task 12），避免被 bleach 剥离。spec 提到 `allowfullscreen` 属性 → plan 简化为只用 `allow`（覆盖现代浏览器 fullscreen），两侧（renderHTML + 白名单）一致不含 allowfullscreen。
- **风险已落入任务**：bleach callable 形态用 tag 级回调（Task 2，确定 bleach 6 支持）；公开详情页精简序列化器（Task 5）；tus 取最新视频的竞态（Task 11 注释）。
