# 展品布展入口挪到详情页 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把展示活动的展品管理(加/删/改/从征集导入)从创建表单挪到详情页,待开始期策展人可布展,开放后冻结;创建表单不再录展品,0 展品可建。

**Architecture:** 后端在 `ActivityViewSet` 加四个命名 detail action(`add_exhibit` / `update_exhibit` / `delete_exhibit` / `import_from_collection`),门禁统一走 `CanModifyActivity` 权限类 + 视图层 `can_edit(activity)`(即 scheduled)校验。展品相关写入逻辑(建 VoteOption、复制文件副本)从现有 `_create_exhibition` 抽成可复用 helper。前端创建表单删展品栏;详情页加「布展」管理面板(策展人 + scheduled 可见),含手动添加与两步式从征集导入。

**Tech Stack:** Django 6 + DRF(后端,`activities/`);React 19 + TypeScript + Webpack(前端,`frontend/src/`);附件复用 `attachments.Attachment`(`exhibit` 父级 FK);测试用 Django `TestCase` + DRF `APIClient`(HTTP 黑盒,`activities/tests.py`)。

**参考 spec:** `docs/superpowers/specs/2026-08-12-exhibit-curation-on-detail-page-design.md`

**任务排序原则(重要):** 先加新动作(helper → add → update/delete → import),此时创建路径仍是旧的 multipart,所有现有测试保持绿,**每个 task 提交时测试全绿**。最后(Task 5)才翻转创建路径到 JSON、迁移 `ExhibitionTest._create` helper、删 `_create_exhibition`,合成一个绿提交。这样不会出现「提交红状态」。

**关键现状(实现时必读,不要假设):**
- `Exhibit.vote_option` 是 `OneToOneField → VoteOption`,`null=True`(`activities/models.py:207`)。启用投票时每展品绑一个选项。
- `Attachment` 有「恰好一个父级」CheckConstraint(`attachments/models.py:72`),`exhibit` 是合法父级;复制/建附件时只设 `exhibit`,其余父级留空。
- `CanModifyActivity`(`activities/permissions.py:23`):`has_permission` 判登录,`has_object_permission` 判 `creator_id == user.pk or has_perm("activities.change_activity")`。挂到 action 的 `permission_classes` 后,DRF 在 `get_object()` 时自动跑对象级校验。
- `can_edit(activity)`(`activities/lifecycle.py:56`):`activity.status == SCHEDULED`。展品管理的「此刻能否管」直接复用它(语义一致:待开始可改,开放锁定)。已在 views.py 顶部 import。
- 文件校验:`upload_error(f)`(`attachments/validation.py`,全局禁用后缀 + 50MB)。已在 views.py import。
- `classify_file_type` 已在 views.py import。
- 现有 `_create_exhibition`(`activities/views.py:127`)在创建时为每展品建 VoteOption + 建附件——Task 1 把这段抽成 helper。
- 前端列表接口支持 `?type=collection` 过滤(`ActivityViewSet.filterset_fields` 含 `type`),无需新后端接口。
- 全套测试目前 494 绿;本计划新增的后端测试挂在 `activities/tests.py` 的 `ExhibitionTest` 类内,沿用其 `_img/_ex/_rate/_vote` helper 与模块级 `_json` 工具函数。

**约定:**
- 后端按 TDD(每个 action 先写 HTTP 黑盒失败测试 → 实现 → 绿 → 提交)。前端无测试运行器,用 `tsc --noEmit` + `npm run build` 验证(每任务末尾跑)。
- 每个 task 结束时 `uv run python manage.py test activities` 必须全绿才提交。
- 命令默认在仓库根 `E:\Backend`;前端命令在 `E:\Backend\frontend`。
- 单测:`uv run python manage.py test activities.tests.ExhibitionTest.<方法名>`;整 app:`uv run python manage.py test activities`。
- 提交信息中文,带 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

---

## 文件结构

**后端:**
- `activities/views.py` — T1 抽 helper;T2-T4 加四个 action;T5 改 `create`/删 `_create_exhibition`/迁移展品测试 helper。
- `activities/tests.py` — T2-T4 加新测试(`_create_empty`/`_add_exhibit`/...);T5 迁移 `_create` + 删过时测试。
- `activities/serializers.py` — T5 加 exhibition 的 K≥1 校验。

**前端:**
- `frontend/src/types/activities.ts` — T6 加 `ExhibitionFormData`。
- `frontend/src/api/activities.ts` — T6 删 `createExhibition`;T7 加 4 个布展 API。
- `frontend/src/pages/ActivityFormPage.tsx` — T6 删展品栏。
- `frontend/src/pages/ActivityDetailPage.tsx` — T7 加布展面板。

**文档:** `CONTEXT.md` — T8 对齐。

---

## Task 1: 后端 — 抽 `_build_exhibit` helper(建展品+附件+可选 VoteOption)

**Files:** Modify `activities/views.py`

**背景:** `add_exhibit`/`import_from_collection` 都要「建一个展品 + 一束附件 + (启用投票时)一个 VoteOption」。这段逻辑现在内联在 `_create_exhibition` 的循环里(~183-191 行)。抽成 helper 给后续 task 复用。**纯重构,行为不变,现有测试保持绿。**

- [ ] **Step 1: 在 `ActivityViewSet` 内加 helper**

在 `activities/views.py` 的 `ActivityViewSet` 内,`_create_exhibition` 方法之前,加:

```python
    def _build_exhibit(self, activity, title, files, voting_enabled):
        """建一个展品 + 一束附件;启用投票时另建一个 VoteOption 并绑定。

        供 _create_exhibition / add_exhibit / import_from_collection 复用。
        files 已经过 upload_error 校验(调用方负责)。
        """
        option = None
        if voting_enabled:
            order = activity.options.count()
            option = VoteOption.objects.create(activity=activity, text=title or "", order=order)
        exhibit = Exhibit.objects.create(activity=activity, title=title, vote_option=option)
        for f in files:
            Attachment.objects.create(
                uploaded_by=self.request.user, exhibit=exhibit, file=f,
                file_type=classify_file_type(f.content_type),
                file_name=f.name, file_size=f.size,
            )
        return exhibit
```

- [ ] **Step 2: 让 `_create_exhibition` 复用 helper**

把 `_create_exhibition` 的循环体(~183-191 行):

```python
            for i, (title, files) in enumerate(exhibits):
                option = None
                if voting_enabled:
                    option = VoteOption.objects.create(activity=activity, text=title, order=i)
                exhibit = Exhibit.objects.create(activity=activity, title=title, vote_option=option)
                for f in files:
                    Attachment.objects.create(
                        uploaded_by=request.user, exhibit=exhibit, file=f,
                        file_type=classify_file_type(f.content_type),
                        file_name=f.name, file_size=f.size,
                    )
```

替换为:

```python
            for i, (title, files) in enumerate(exhibits):
                self._build_exhibit(activity, title, files, voting_enabled)
```

(创建循环里逐个建时,`activity.options.count()` 给出 0,1,2...,与原 `i` 等价。)

- [ ] **Step 3: 跑整 app 确认行为不变**

Run: `uv run python manage.py test activities 2>&1 | tail -6`
Expected: 全绿(与抽 helper 前数量一致,~93 个 activities 测试)。

- [ ] **Step 4: 提交**

```bash
git add activities/views.py
git commit -m "refactor(activities): 抽 _build_exhibit helper（布展 #1/8）

建展品+附件+(启用投票时)VoteOption 的逻辑从 _create_exhibition 抽出,
供 add_exhibit / import_from_collection 复用。行为不变。"
```

---

## Task 2: 后端 — `add_exhibit` 动作(手动加一个展品)

**Files:** Modify `activities/views.py`, `activities/tests.py`

**门禁:** `[IsAuthenticated(), CanModifyActivity()]` + 视图层 `can_edit(activity)`(scheduled)。
**输入:** multipart `title`(选填)+ `files`(一束,必传)。
**行为:** 校验文件 → `_build_exhibit(activity, title, files, activity.voting_enabled)`。

- [ ] **Step 1: 在 `ExhibitionTest` 加 fixture helper**

在 `activities/tests.py` 的 `ExhibitionTest` 类内,`_create` 方法之后加(这些 helper 给新流程用,不影响旧 `_create`):

```python
    def _create_empty(self, user, voting_enabled="false", **scalar):
        """建一个 0 展品的展示(展品改在详情页布展)。返回 response。

        start_at 默认不给 → status=open。给 start_at(未来)→ scheduled。
        """
        body = {"type": "exhibition", "title": "影展", "body": "<p>x</p>",
                "voting_enabled": voting_enabled}
        body.update(scalar)
        self.client.force_authenticate(user)
        return self.client.post("/activities/activities/", data=body,
                                content_type="application/json")

    def _add_exhibit(self, user, aid, title="", files=None):
        files = files or [self._img()]
        fd = {}
        if title:
            fd["title"] = title
        for f in files:
            fd.setdefault("files", []).append(f)
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{aid}/add_exhibit/", data=fd)
```

- [ ] **Step 2: 写失败测试 — happy path + 文件必传 + 投票建选项**

在 `ExhibitionTest` 内(投票测试区之前)加:

```python
    # ---- 详情页布展:add_exhibit(待开始期手动加展品)----

    def test_add_exhibit_creates_exhibit_with_files(self):
        ex = self._create_empty(self.curator, voting_enabled="false")
        aid = ex.data["id"]
        r = self._add_exhibit(self.curator, aid, title="作品A",
                              files=[self._img(), self._img("b.png")])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"]), 1)
        e = r.data["exhibits"][0]
        self.assertEqual(e["title"], "作品A")
        self.assertEqual(len(e["files"]), 2)
        self.assertIsNone(e["vote_option_id"])  # 未启用投票:无选项

    def test_add_exhibit_voting_enabled_builds_option(self):
        ex = self._create_empty(self.curator, voting_enabled="true",
                                max_choices_per_voter=1)
        aid = ex.data["id"]
        r = self._add_exhibit(self.curator, aid, title="X")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data["exhibits"][0]["vote_option_id"])

    def test_add_exhibit_requires_file(self):
        ex = self._create_empty(self.curator)
        r = self._add_exhibit(self.curator, ex.data["id"], files=[])
        self.assertEqual(r.status_code, 400)
```

- [ ] **Step 3: 跑确认失败**

Run: `uv run python manage.py test activities.tests.ExhibitionTest.test_add_exhibit_creates_exhibit_with_files activities.tests.ExhibitionTest.test_add_exhibit_voting_enabled_builds_option activities.tests.ExhibitionTest.test_add_exhibit_requires_file`
Expected: FAIL(404 — `add_exhibit` 路由不存在)。

- [ ] **Step 4: 实现 `add_exhibit` action**

在 `activities/views.py` 的 `rate` action 之前加:

```python
    # ── 展示:详情页布展(待开始期加/改/删/导入展品)──
    @action(detail=True, methods=["post"], url_path="add_exhibit")
    def add_exhibit(self, request, pk=None):
        activity = self.get_object()
        if activity.type != "exhibition":
            return Response({"detail": "仅展示可加展品"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_edit(activity):
            return Response({"detail": "展示开放后不可改展品"}, status=status.HTTP_400_BAD_REQUEST)
        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "展品至少需要 1 个文件"}, status=status.HTTP_400_BAD_REQUEST)
        for f in files:
            err = upload_error(f)
            if err:
                return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
        title = (request.data.get("title") or "").strip()
        with transaction.atomic():
            self._build_exhibit(activity, title, files, activity.voting_enabled)
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)
```

并在 `get_permissions()` 的 `close` 分支之后加:

```python
        if self.action in ("add_exhibit", "update_exhibit", "delete_exhibit", "import_from_collection"):
            return [IsAuthenticated(), CanModifyActivity()]
```

- [ ] **Step 5: 跑这 3 个测试确认通过**

Run: 同 Step 3 命令。Expected: 3 PASS。

- [ ] **Step 6: 加状态/权限门禁测试**

```python
    def test_add_exhibit_blocked_when_open(self):
        # 未排期 → 创建即 open → 不可布展
        ex = self._create_empty(self.curator)
        r = self._add_exhibit(self.curator, ex.data["id"], title="A")
        self.assertEqual(r.status_code, 400)

    def test_add_exhibit_non_curator_forbidden(self):
        ex = self._create_empty(self.curator)
        r = self._add_exhibit(self.member, ex.data["id"], title="A")
        self.assertEqual(r.status_code, 403)

    def test_add_exhibit_scheduled_allowed(self):
        from datetime import datetime, timedelta, timezone as dtz
        start = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        ex = self._create_empty(self.curator, start_at=start)
        self.assertEqual(ex.data["status"], "scheduled")
        r = self._add_exhibit(self.curator, ex.data["id"], title="A")
        self.assertEqual(r.status_code, 200)
```

- [ ] **Step 7: 跑整 app 全绿**

Run: `uv run python manage.py test activities 2>&1 | tail -6`
Expected: 全绿(旧测试不受影响 + 6 个新 add_exhibit 测试)。

- [ ] **Step 8: 提交**

```bash
git add activities/views.py activities/tests.py
git commit -m "feat(activities): add_exhibit 动作——详情页手动加展品（布展 #2/8）

策展人(发起人 or change_activity)在待开始期往展示加展品(multipart:
title + files);启用投票时建 VoteOption。开放后拒绝(can_edit)。"
```

---

## Task 3: 后端 — `delete_exhibit` + `update_exhibit`

**Files:** Modify `activities/views.py`, `activities/tests.py`

两个动作一起做,各自 RED→GREEN,一个提交。

### 3A: `delete_exhibit`

- [ ] **Step 3A.1: 写失败测试**

在 `ExhibitionTest` 加:

```python
    def _delete_exhibit(self, user, aid, eid):
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{aid}/delete_exhibit/",
                                data={"exhibit_id": eid})

    def test_delete_exhibit_removes_it_and_option(self):
        from datetime import datetime, timedelta, timezone as dtz
        start = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        ex = self._create_empty(self.curator, voting_enabled="true",
                                max_choices_per_voter=1, start_at=start)
        aid = ex.data["id"]
        self._add_exhibit(self.curator, aid, title="A")
        eid = self.client.get(f"/activities/activities/{aid}/").data["exhibits"][0]["id"]
        r = self._delete_exhibit(self.curator, aid, eid)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"]), 0)
        from .models import VoteOption
        self.assertEqual(VoteOption.objects.filter(activity_id=aid).count(), 0)

    def test_delete_exhibit_open_blocked(self):
        ex = self._create_empty(self.curator, voting_enabled="true")  # open
        r = self._delete_exhibit(self.curator, ex.data["id"], 999)
        self.assertEqual(r.status_code, 400)  # 开放态拒绝(在「展品不存在」前先撞状态门)
```

- [ ] **Step 3A.2: 跑确认失败** — Run: `uv run python manage.py test activities.tests.ExhibitionTest.test_delete_exhibit_removes_it_and_option activities.tests.ExhibitionTest.test_delete_exhibit_open_blocked` → FAIL(404)。

- [ ] **Step 3A.3: 实现 delete_exhibit**(在 `add_exhibit` 之后)

```python
    @action(detail=True, methods=["post"], url_path="delete_exhibit")
    def delete_exhibit(self, request, pk=None):
        activity = self.get_object()
        if activity.type != "exhibition":
            return Response({"detail": "仅展示可删展品"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_edit(activity):
            return Response({"detail": "展示开放后不可改展品"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exhibit = activity.exhibits.get(pk=request.data.get("exhibit_id"))
        except (Exhibit.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "展品不存在"}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            if exhibit.vote_option_id:
                VoteOption.objects.filter(pk=exhibit.vote_option_id).delete()
            exhibit.delete()  # 连带删附件(CASCADE)+ 回收文件(post_delete 信号)
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)
```

- [ ] **Step 3A.4: 跑确认通过** → 2 PASS。

### 3B: `update_exhibit`(改标题 + 整体覆盖文件)

- [ ] **Step 3B.1: 写失败测试**

```python
    def _update_exhibit(self, user, aid, eid, title=None, files=None):
        fd = {"exhibit_id": str(eid)}
        if title is not None:
            fd["title"] = title
        if files:
            for f in files:
                fd.setdefault("files", []).append(f)
        self.client.force_authenticate(user)
        return self.client.post(f"/activities/activities/{aid}/update_exhibit/",
                                data=fd, format="multipart")

    def test_update_exhibit_renames_and_syncs_option(self):
        from datetime import datetime, timedelta, timezone as dtz
        start = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        ex = self._create_empty(self.curator, voting_enabled="true",
                                max_choices_per_voter=1, start_at=start)
        aid = ex.data["id"]
        self._add_exhibit(self.curator, aid, title="旧名")
        eid = self.client.get(f"/activities/activities/{aid}/").data["exhibits"][0]["id"]
        r = self._update_exhibit(self.curator, aid, eid, title="新名")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["exhibits"][0]["title"], "新名")
        from .models import VoteOption
        self.assertEqual(VoteOption.objects.get(activity_id=aid).text, "新名")

    def test_update_exhibit_replaces_files(self):
        from datetime import datetime, timedelta, timezone as dtz
        start = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        ex = self._create_empty(self.curator, start_at=start)
        aid = ex.data["id"]
        self._add_exhibit(self.curator, aid, files=[self._img("a.png"), self._img("b.png")])
        eid = self.client.get(f"/activities/activities/{aid}/").data["exhibits"][0]["id"]
        r = self._update_exhibit(self.curator, aid, eid, files=[self._img("c.png")])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"][0]["files"]), 1)
        self.assertEqual(r.data["exhibits"][0]["files"][0]["file_name"], "c.png")
```

- [ ] **Step 3B.2: 跑确认失败** → FAIL(404)。

- [ ] **Step 3B.3: 实现 update_exhibit**(在 `delete_exhibit` 之后)

```python
    @action(detail=True, methods=["post"], url_path="update_exhibit")
    def update_exhibit(self, request, pk=None):
        activity = self.get_object()
        if activity.type != "exhibition":
            return Response({"detail": "仅展示可改展品"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_edit(activity):
            return Response({"detail": "展示开放后不可改展品"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exhibit = activity.exhibits.get(pk=request.data.get("exhibit_id"))
        except (Exhibit.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "展品不存在"}, status=status.HTTP_404_NOT_FOUND)
        files = request.FILES.getlist("files")
        for f in files:
            err = upload_error(f)
            if err:
                return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
        title = request.data.get("title")
        with transaction.atomic():
            if title is not None:
                exhibit.title = title.strip()
                if exhibit.vote_option_id:
                    VoteOption.objects.filter(pk=exhibit.vote_option_id).update(text=exhibit.title)
            if files:
                exhibit.attachments.all().delete()  # 旧文件回收(CASCADE + post_delete 信号)
                for f in files:
                    Attachment.objects.create(
                        uploaded_by=request.user, exhibit=exhibit, file=f,
                        file_type=classify_file_type(f.content_type),
                        file_name=f.name, file_size=f.size,
                    )
            if title is not None:
                exhibit.save(update_fields=["title"])
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)
```

- [ ] **Step 3B.4: 跑确认通过** → 2 PASS。

- [ ] **Step 3B.5: 跑整 app 全绿**

Run: `uv run python manage.py test activities 2>&1 | tail -6`
Expected: 全绿(+ 4 个新测试)。

- [ ] **Step 3B.6: 提交**

```bash
git add activities/views.py activities/tests.py
git commit -m "feat(activities): delete_exhibit + update_exhibit（布展 #3/8）

delete_exhibit 连带删绑定 VoteOption;update_exhibit 改标题同步选项文本 +
整体覆盖文件(旧附件回收)。统一门禁 CanModifyActivity + can_edit(scheduled)。"
```

---

## Task 4: 后端 — `import_from_collection`(从征集复制任意作品,独立副本)

**Files:** Modify `activities/views.py`, `activities/tests.py`

- [ ] **Step 1: 在 `ExhibitionTest` 加 collection fixture helper**

```python
    def _make_collection_with_submissions(self, owner, n=2):
        """建一个征集并提交 n 个作品(含文件),返回 (activity_id, [submission_id])。"""
        self.client.force_authenticate(owner)
        c = self.client.post("/activities/activities/", data={
            "type": "collection", "title": "征", "body": "<p>x</p>",
            "review_enabled": "false",  # 跳过复审,作品直接公开可见
        }, content_type="application/json")
        cid = c.data["id"]
        sub_ids = []
        submitters = [self.member, self.m2]
        for i in range(n):
            fd = {"files": [self._img(f"s{i}.png")]}
            self.client.force_authenticate(submitters[i % len(submitters)])
            r = self.client.post(f"/activities/activities/{cid}/submit/", data=fd)
            sub_ids.append(r.data["my_submission"]["id"])
        return cid, sub_ids
```

- [ ] **Step 2: 写失败测试**

```python
    def test_import_from_collection_copies_selected(self):
        from datetime import datetime, timedelta, timezone as dtz
        start = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        cid, sub_ids = self._make_collection_with_submissions(self.curator, n=2)
        ex = self._create_empty(self.curator, voting_enabled="false", start_at=start)
        aid = ex.data["id"]
        self.client.force_authenticate(self.curator)
        r = self.client.post(f"/activities/activities/{aid}/import_from_collection/",
                             data={"collection_id": cid, "submission_ids": sub_ids},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["exhibits"]), 2)
        files = [f for e in r.data["exhibits"] for f in e["files"]]
        self.assertEqual(len(files), 2)

    def test_import_invalid_collection(self):
        start = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        ex = self._create_empty(self.curator, start_at=start)
        self.client.force_authenticate(self.curator)
        r = self.client.post(f"/activities/activities/{ex.data['id']}/import_from_collection/",
                             data={"collection_id": 999999, "submission_ids": []},
                             content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_import_is_independent_snapshot(self):
        # 复制成独立副本:原作品附件删了,展品文件仍在
        from datetime import datetime, timedelta, timezone as dtz
        start = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        cid, sub_ids = self._make_collection_with_submissions(self.curator, n=1)
        ex = self._create_empty(self.curator, start_at=start)
        aid = ex.data["id"]
        self.client.force_authenticate(self.curator)
        self.client.post(f"/activities/activities/{aid}/import_from_collection/",
                         data={"collection_id": cid, "submission_ids": sub_ids},
                         content_type="application/json")
        from .models import Submission
        Submission.objects.get(pk=sub_ids[0]).attachments.all().delete()
        detail = self.client.get(f"/activities/activities/{aid}/").data
        self.assertEqual(len(detail["exhibits"][0]["files"]), 1)
```

- [ ] **Step 3: 跑确认失败** — Run: `uv run python manage.py test activities.tests.ExhibitionTest.test_import_from_collection_copies_selected activities.tests.ExhibitionTest.test_import_invalid_collection activities.tests.ExhibitionTest.test_import_is_independent_snapshot` → FAIL(404)。

- [ ] **Step 4: 实现 import_from_collection**(在 `update_exhibit` 之后)

```python
    @action(detail=True, methods=["post"], url_path="import_from_collection")
    def import_from_collection(self, request, pk=None):
        from django.core.files.base import ContentFile

        activity = self.get_object()
        if activity.type != "exhibition":
            return Response({"detail": "仅展示可导入"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_edit(activity):
            return Response({"detail": "展示开放后不可改展品"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            source = Activity.objects.get(pk=request.data.get("collection_id"), type="collection")
        except (Activity.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "征集不存在"}, status=status.HTTP_404_NOT_FOUND)
        submission_ids = request.data.get("submission_ids") or []
        subs = source.submissions.filter(pk__in=submission_ids)
        if not subs:
            return Response({"detail": "未选择任何作品"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for sub in subs:
                exhibit = self._build_exhibit(activity, "", [], activity.voting_enabled)
                for a in sub.attachments.all():
                    new_att = Attachment(
                        uploaded_by=request.user, exhibit=exhibit,
                        file_type=a.file_type, file_name=a.file_name, file_size=a.file_size,
                    )
                    new_att.file.save(a.file.name, ContentFile(a.file.read()))
                    new_att.save()
        activity = self.get_queryset().get(pk=activity.pk)
        return Response(ActivityDetailSerializer(activity, context={"request": request}).data)
```

(`_build_exhibit(activity, "", [], ...)` 传空文件列表,文件走下面的复制循环;helper 内 `for f in []` 跳过。`voting_enabled` 时 helper 建一个 text="" 的 VoteOption。)

- [ ] **Step 5: 跑这 3 个测试确认通过**

Run: 同 Step 3 命令。Expected: 3 PASS。

- [ ] **Step 6: 跑整 app 全绿**

Run: `uv run python manage.py test activities 2>&1 | tail -6`
Expected: 全绿(+ 3 个新测试)。

- [ ] **Step 7: 提交**

```bash
git add activities/views.py activities/tests.py
git commit -m "feat(activities): import_from_collection——从征集勾选任意作品导入（布展 #4/8）

策展人在待开始期选一个征集,勾选其任意状态的作品,复制成独立展品副本
(文件独立存储)。启用投票时每展品建选项。"
```

---

## Task 5: 后端 — 翻转创建路径到 JSON + 迁移测试 + 删 `_create_exhibition`

**Files:** Modify `activities/views.py`, `activities/serializers.py`, `activities/tests.py`

**这是合并点:** 此时四个新动作都已就位,把创建从 multipart 翻到 JSON、把旧 `_create` helper 迁移到「建空展 + add_exhibit」、删 `_create_exhibition`、补 K≥1 校验——合成一个绿提交。

- [ ] **Step 1: 改 `create()` 不再对 exhibition 分流**

`activities/views.py`,把:

```python
    def create(self, request, *args, **kwargs):
        # 展示:展品在创建时录入（multipart：每展品一束文件），与 JSON 创建路径分流。
        if request.data.get("type") == "exhibition":
            return self._create_exhibition(request)
        return super().create(request, *args, **kwargs)
```

改成:

```python
    def create(self, request, *args, **kwargs):
        # 展示:展品在详情页布展(待开始期),创建只收标量——0 展品可建,走 JSON 通用路径。
        return super().create(request, *args, **kwargs)
```

- [ ] **Step 2: 删 `_create_exhibition` 方法**

删 `activities/views.py` 里整个 `_create_exhibition` 方法(~127-197 行,含其内部的 `_parse_int/_parse_bool`)。确认无引用:

Run: `grep -rn "_create_exhibition" activities/`(应无结果)。

- [ ] **Step 3: 序列化器加 exhibition 的 K≥1 校验**

`activities/serializers.py` 的 `validate` 方法,在 `if is_delib: ...` 块之后(`return attrs` 之前)加:

```python
        is_exhib = attrs.get("type") == "exhibition" or (
            self.instance is not None and self.instance.type == "exhibition"
        )
        if is_exhib and attrs.get("voting_enabled"):
            k = attrs.get("max_choices_per_voter", getattr(self.instance, "max_choices_per_voter", 1))
            if k < 1:
                raise serializers.ValidationError(
                    {"max_choices_per_voter": "每人最多选几项至少为 1"}
                )
```

- [ ] **Step 4: 重写 `ExhibitionTest._create` helper(用新流程)**

把 `ExhibitionTest._create`(当前发 multipart 那个)整体替换为「建排期空展 + add_exhibit 布展 + 翻 open」:

```python
    def _create(self, user, exhibits, **scalar):
        """建展示 + 待开始期布展 + 翻 open。exhibits: [(title, [SimpleUploadedFile...]), ...]

        新流程:排期到未来(→scheduled)→ add_exhibit 逐个加展品 → 把 start_at 改到
        过去并 GET 触发 transition_due_starts(→open)。对外契约不变:返回带 exhibits
        的 open 态 response(投票/赞踩测试可直接用)。
        """
        from datetime import datetime, timedelta, timezone as dtz
        start_future = (datetime.now(dtz.utc) + timedelta(days=1)).isoformat()
        body = {"type": "exhibition", "title": "影展", "body": "<p>x</p>",
                "voting_enabled": "true", "start_at": start_future}
        body.update(scalar)
        self.client.force_authenticate(user)
        r = self.client.post("/activities/activities/", data=body, content_type="application/json")
        assert r.status_code == 201, r.data
        aid = r.data["id"]
        assert r.data["status"] == "scheduled", r.data
        for title, files in exhibits:
            ar = self._add_exhibit(user, aid, title=title, files=files)
            assert ar.status_code == 200, ar.data
        from .models import Activity
        Activity.objects.filter(pk=aid).update(
            start_at=datetime.now(dtz.utc) - timedelta(hours=1))
        r2 = self.client.get(f"/activities/activities/{aid}/")
        assert r2.data["status"] == "open", r2.data
        return r2
```

- [ ] **Step 5: 删/迁过时测试**

在 `ExhibitionTest` 内:
- **删** `test_create_with_exhibits`(展品改详情页)
- **删** `test_requires_at_least_one_exhibit`(0 展品可建)
- **删** `test_exhibit_requires_file`(文件校验移到 add_exhibit,已有 `test_add_exhibit_requires_file`)
- **删** `test_create_voting_disabled_builds_no_options`(#55 语义,由 add_exhibit 系列覆盖)
- **删** `test_create_voting_disabled_ignores_k`(同上)
- **删** `test_k_above_exhibit_count_rejected`(创建时展品数为 0,此校验不再适用;K≥1 由新测试覆盖)

- [ ] **Step 6: 加 K≥1 创建校验测试**

```python
    def test_create_voting_enabled_k_at_least_1(self):
        self.client.force_authenticate(self.curator)
        r = self.client.post("/activities/activities/", data={
            "type": "exhibition", "title": "t", "body": "",
            "voting_enabled": "true", "max_choices_per_voter": 0,
        }, content_type="application/json")
        self.assertEqual(r.status_code, 400)
```

- [ ] **Step 7: 跑整 ExhibitionTest,逐个确认绿**

Run: `uv run python manage.py test activities.tests.ExhibitionTest 2>&1 | tail -15`

**预期:** 绝大多数旧测试(投票/赞踩/生命周期)经 Step 4 的 `_create` 重写后自动绿(对外契约:open 态 + exhibits 不变)。若有个别红(如 `test_closed_blocks_vote_and_rate` 依赖 end_at、`test_secret_exhibition_hides_ballots`),读错误信息逐个修——通常是断言 `r.data` 顶层而非 `exhibits` 的小差异。

- [ ] **Step 8: 跑整 app 全绿**

Run: `uv run python manage.py test activities 2>&1 | tail -6`
Expected: 全绿。

- [ ] **Step 9: `manage.py check` + 迁移检查**

Run: `uv run python manage.py check && uv run python manage.py makemigrations --check --dry-run`
Expected: `System check identified no issues.` + `No changes detected`(无新字段,不应有迁移)。

- [ ] **Step 10: 提交**

```bash
git add activities/views.py activities/serializers.py activities/tests.py
git commit -m "refactor(activities): 创建路径翻 JSON + 迁移展品测试 + 删 _create_exhibition（布展 #5/8）

create() 不再分流到 multipart;展示创建走 JSON 标量(0 展品可建)。ExhibitionTest
._create 改为「建空展 + add_exhibit + 翻 open」;删创建时展品校验的过时测试;
exhibition 的 K>=1 校验移到序列化器。_create_exhibition 视图方法删除。"
```

---

## Task 6: 后端 — 全套测试 + /code-review

**Files:** 无(验证 + 修复)

- [ ] **Step 1: 全量测试**

Run: `uv run python manage.py test 2>&1 | tail -8`
Expected: 全绿。

- [ ] **Step 2: /code-review**

用 `/code-review` skill,固定点为本计划开始前的 commit(`0888c60` 即 #55 合入后,或 `git merge-base HEAD main`)。修发现的问题(重点关注:门禁是否真用 `can_edit`、helper 复用是否 DRY、import 文件复制是否真独立)。

- [ ] **Step 3: 提交复核修复(若有)**

---

## Task 7: 前端 — 创建表单删展品栏 + 加布展 API

**Files:** Modify `frontend/src/types/activities.ts`, `frontend/src/api/activities.ts`, `frontend/src/pages/ActivityFormPage.tsx`

**说明:** 前端原计划拆成「表单(T7)」+「详情页(T8)」两 task,但表单改动与 4 个布展 API 自然成组(API 给 T8 用)。本 task 同时做表单简化 + 加 API 方法 + 类型;详情页 UI 单独 T8。

- [ ] **Step 1: 类型 — 加 `ExhibitionFormData`**

`frontend/src/types/activities.ts`,把:

```typescript
// 展示走 multipart（展品在创建时录入），不经 JSON 创建路径——表单内用本地状态组装 FormData。
export type ActivityFormData = DeliberationFormData | CollectionFormData;
```

改成:

```typescript
export interface ExhibitionFormData {
  type: "exhibition";
  title: string;
  body: string;
  voting_enabled: boolean;
  max_choices_per_voter: number; // 启用投票时有意义
  is_secret_ballot: boolean;
  start_at?: string;
  end_at?: string;
}

// 众议/征集/展示均走 JSON 创建标量(展品改在详情页 add_exhibit 录入)。
export type ActivityFormData = DeliberationFormData | CollectionFormData | ExhibitionFormData;
```

- [ ] **Step 2: API — 删 `createExhibition` + 加 4 个布展方法**

`frontend/src/api/activities.ts`:

删 `createExhibition` 方法(multipart 创建已废)。

在 `rate` 方法之后加:

```typescript
  // 展示布展(待开始期):手动加展品(multipart: title + files)
  addExhibit: (id: number, title: string, files: File[]): Promise<ActivityDetail> => {
    const fd = new FormData();
    if (title) fd.append("title", title);
    for (const f of files) fd.append("files", f);
    return request(`/activities/${id}/add_exhibit/`, { method: "POST", body: fd });
  },

  // 改展品(title 给了就改 + 同步选项;files 给了就整体覆盖)
  updateExhibit: (id: number, exhibitId: number, title: string | null, files: File[] | null): Promise<ActivityDetail> => {
    const fd = new FormData();
    fd.append("exhibit_id", String(exhibitId));
    if (title != null) fd.append("title", title);
    if (files) for (const f of files) fd.append("files", f);
    return request(`/activities/${id}/update_exhibit/`, { method: "POST", body: fd });
  },

  // 删展品(连带删附件 + 绑定选项)
  deleteExhibit: (id: number, exhibitId: number): Promise<ActivityDetail> =>
    request(`/activities/${id}/delete_exhibit/`, {
      method: "POST",
      body: JSON.stringify({ exhibit_id: exhibitId }),
    }),

  // 从征集导入(勾选任意作品,复制独立副本)
  importFromCollection: (id: number, collectionId: number, submissionIds: number[]): Promise<ActivityDetail> =>
    request(`/activities/${id}/import_from_collection/`, {
      method: "POST",
      body: JSON.stringify({ collection_id: collectionId, submission_ids: submissionIds }),
    }),
```

- [ ] **Step 3: ActivityFormPage — 删展品 state + helper**

`frontend/src/pages/ActivityFormPage.tsx`:

删 `exhibits` state 行:

```typescript
  const [exhibits, setExhibits] = useState<{ title: string; files: File[] }[]>([
    { title: "", files: [] },
  ]);
```

(保留 `votingEnabled` state。)

`switchType` 去掉对 `exhibits`/`votingEnabled` 的重置(留 votingEnabled?——投票开关跟类型无关,切类型时不重置无所谓;但为干净,切到非展示时可不动。简化:switchType 只留 setType + setEndAt):

```typescript
  const switchType = (t: ActivityType) => {
    setType(t);
    setEndAt(defaultEnd(t === "deliberation" ? 3 : 7));
  };
```

删 `setExhibit` helper 整段。

- [ ] **Step 4: ActivityFormPage — 删 submit() 展品校验块**

删 submit 函数里展示分支的展品校验(`if (!editId) { ... exhibits ... }` 整块),使展示分支无额外创建校验(标题已在顶部统一校验):

把:

```typescript
      } else {
        // 展示：展品在创建时录入（编辑模式展品已冻结，仅改标量）
        if (!editId) {
          if (exhibits.length < 1) {
            setError("展示至少需要 1 个展品");
            return;
          }
          for (let i = 0; i < exhibits.length; i++) {
            if (exhibits[i].files.length < 1) {
              setError(`展品「${exhibits[i].title.trim() || i + 1}」至少需要 1 个文件`);
              return;
            }
          }
          // #56：仅启用投票时校验 K；纯陈列不投票，K 无意义。
          if (votingEnabled && (k < 1 || k > exhibits.length)) {
            setError(`每人最多选几项须在 1..${exhibits.length} 之间`);
            return;
          }
        }
      }
```

替换为:

```typescript
      }
      // 展示:创建/编辑只带标量(展品在详情页布展);无额外校验(K>=1 由后端序列化器把关)
```

- [ ] **Step 5: ActivityFormPage — 改展示创建/编辑为 JSON**

把展示分支的提交逻辑(原 `else if (editId) { ... } else { multipart FormData ... }`):

```typescript
      } else if (editId) {
        // 展示编辑：展品与投票开关均已冻结...
        saved = await activityApi.update(editId, { type: "exhibition", ... });
      } else {
        // 展示创建：multipart...
        const fd = new FormData();
        ...
        saved = await activityApi.createExhibition(fd);
      }
```

整体替换为:

```typescript
      } else {
        // 展示创建/编辑:JSON 标量(展品改在详情页 add_exhibit)
        const payload: ExhibitionFormData = {
          type: "exhibition",
          title: title.trim(),
          body,
          voting_enabled: votingEnabled,
          max_choices_per_voter: k,
          is_secret_ballot: secret,
          start_at: toIso(startAt),
          end_at: toIso(endAt),
        };
        saved = editId
          ? await activityApi.update(editId, payload)
          : await activityApi.create(payload);
      }
```

文件顶部 import 改:

```typescript
import type { ActivityType, ExhibitionFormData } from "../types/activities";
```

- [ ] **Step 6: ActivityFormPage — 删展示分支 JSX 的展品编辑器**

在 return 的 JSX 里,展示分支(`: ( <> ... </> )`)替换为(删展品编辑器 + 冻结 alert,留截止 + 启用投票 + K/秘密):

```tsx
          ) : (
            <>
              {/* 展示：截止 + 启用投票开关（展品在详情页布展） */}
              <div className="field">
                <label className="label">展示截止</label>
                <input className="input" type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} />
              </div>
              <div className="field">
                <label className="fb-attrib">
                  <input
                    type="checkbox"
                    checked={votingEnabled}
                    disabled={!!editId}
                    onChange={(e) => setVotingEnabled(e.target.checked)}
                  />
                  <span>
                    启用投票 —— 勾选：成员可对展品投票（1..K）；不勾：纯陈列，仅展品 + 赞/踩。展品在创建后于详情页录入。
                    {editId && <span className="hint">（投票开关创建后不可改）</span>}
                  </span>
                </label>
              </div>
              {votingEnabled && (
                <div className="form-grid">
                  <div className="field">
                    <label className="label">每人最多投几项（K）</label>
                    <input className="input" type="number" min={1} value={k} onChange={(e) => setK(parseInt(e.target.value, 10) || 1)} />
                    <div className="hint">对展品投票：K=1 一人一展品；K&gt;1 一人最多投 K 个展品。赞/踩另算，可随时改。</div>
                  </div>
                  <div className="field">
                    <label className="fb-attrib" style={{ marginTop: 28 }}>
                      <input type="checkbox" checked={secret} onChange={(e) => setSecret(e.target.checked)} />
                      <span>秘密投票</span>
                    </label>
                  </div>
                </div>
              )}
            </>
          )}
```

- [ ] **Step 7: tsc + build**

Run:
```bash
cd frontend && npx tsc --noEmit && npm run build
```
Expected: 0 exit(两条 bundle-size 警告是既有的,忽略)。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/types/activities.ts frontend/src/api/activities.ts frontend/src/pages/ActivityFormPage.tsx
git commit -m "feat(activities-fe): 创建表单删展品栏 + 布展 API（布展 #7/8）

展品录入改在详情页;创建表单展示分支只剩截止 + 启用投票(K/秘密)。创建/编辑
走 JSON 标量(activityApi.create/update)。加 addExhibit/updateExhibit/
deleteExhibit/importFromCollection 四个 API。删 createExhibition multipart API。"
```

---

## Task 8: 前端 — 详情页「布展」管理面板

**Files:** Modify `frontend/src/pages/ActivityDetailPage.tsx`

- [ ] **Step 1: 加 import + state**

`frontend/src/pages/ActivityDetailPage.tsx` 顶部 import 改(加 `ActivityListItem`):

```typescript
import {
  ActivityDetail,
  ActivityListItem,
  ACTIVITY_TYPE_META,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_BADGE_CLASS,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_BADGE_CLASS,
} from "../types/activities";
```

在组件 state 区(`busy` 附近)加:

```typescript
  // 展示布展(策展人 + 待开始):手动添加 / 改 / 删 / 从征集导入
  const [newTitle, setNewTitle] = useState("");
  const [newFiles, setNewFiles] = useState<File[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const [collections, setCollections] = useState<ActivityListItem[]>([]);
  const [pickedCollection, setPickedCollection] = useState<number | null>(null);
  const [pickedSubs, setPickedSubs] = useState<number[]>([]);
  const [collectionDetail, setCollectionDetail] = useState<ActivityDetail | null>(null);
```

- [ ] **Step 2: 加布展 handler**

在 `doRate` 之后加:

```typescript
  const canCurate = isExhibition && canManage && a.status === "scheduled";

  const doAddExhibit = async () => {
    if (newFiles.length < 1) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.addExhibit(a.id, newTitle.trim(), newFiles)); setNewTitle(""); setNewFiles([]); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const doUpdateExhibit = async (eid: number, curTitle: string) => {
    const t = window.prompt("修改展品标题（留空则不变）：", curTitle);
    if (t === null) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.updateExhibit(a.id, eid, t, null)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const doDeleteExhibit = async (eid: number) => {
    if (!window.confirm("删除该展品？")) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.deleteExhibit(a.id, eid)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const openImport = async () => {
    setImportOpen(true);
    const list = await activityApi.list({ type: "collection" });
    setCollections(list.results);
    if (list.results.length > 0) {
      setPickedCollection(list.results[0].id);
      setCollectionDetail(await activityApi.get(list.results[0].id));
    }
  };
  const pickCollection = async (cid: number) => {
    setPickedCollection(cid);
    setPickedSubs([]);
    setCollectionDetail(await activityApi.get(cid));
  };
  const doImport = async () => {
    if (pickedSubs.length < 1 || pickedCollection == null) return;
    setBusy(true); setError("");
    try { setActivity(await activityApi.importFromCollection(a.id, pickedCollection, pickedSubs)); setImportOpen(false); setPickedSubs([]); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
```

- [ ] **Step 3: 渲染布展面板(展品画廊 card 内,`<h3>展品</h3>` 后、`{canVote && ...}` 前)**

在 `{isExhibition && (() => { ... })}` 的 IIFE 内,`<h3 className="section-h">展品 ({a.exhibits?.length || 0})</h3>` 之后插入:

```tsx
                {canCurate && (
                  <div className="alert alert-info" style={{ marginBottom: 12 }}>
                    <span>布展中（待开始）——可加 / 改 / 删展品，或从征集导入。开放后冻结。</span>
                    <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      <input className="input" style={{ flex: "1 1 160px" }} value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="新展品标题（选填）" />
                      <input type="file" multiple onChange={(e) => setNewFiles(Array.from(e.target.files || []))} />
                      <button className="btn btn-primary btn-sm" onClick={doAddExhibit} disabled={busy || newFiles.length < 1}>+ 加展品</button>
                      <button className="btn btn-ghost btn-sm" onClick={openImport}>从征集导入</button>
                    </div>
                  </div>
                )}
                {importOpen && collectionDetail && (
                  <div className="card card-pad" style={{ margin: "12px 0", background: "var(--c-surface-2, #f9fafb)" }}>
                    <h4 className="section-h">从征集导入</h4>
                    <div className="field">
                      <label className="label">选择征集</label>
                      <select className="input" value={pickedCollection ?? ""} onChange={(e) => pickCollection(Number(e.target.value))}>
                        {collections.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                      </select>
                    </div>
                    {collectionDetail.submissions && collectionDetail.submissions.length > 0 ? (
                      <>
                        <div className="hint" style={{ marginBottom: 8 }}>勾选要导入的作品（任意状态均可，复制成独立副本）。</div>
                        {collectionDetail.submissions.map((s) => {
                          const on = pickedSubs.includes(s.id);
                          return (
                            <label key={s.id} className={"vote-opt" + (on ? " is-on" : "")} style={{ marginBottom: 6 }}>
                              <input type="checkbox" checked={on} onChange={() => setPickedSubs((cur) => on ? cur.filter((x) => x !== s.id) : [...cur, s.id])} />
                              <span className="vote-opt-text">{`@${s.submitter.username}`} · {s.files.length} 个文件</span>
                            </label>
                          );
                        })}
                        <button className="btn btn-primary btn-sm" onClick={doImport} disabled={busy || pickedSubs.length < 1}>导入 {pickedSubs.length} 件</button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setImportOpen(false)}>取消</button>
                      </>
                    ) : (
                      <p className="muted">该征集暂无可见作品。</p>
                    )}
                  </div>
                )}
```

- [ ] **Step 4: 展品卡内加改/删按钮(仅 canCurate)**

在每个 `exhibit-card` 内、`<div className="exhibit-rate">...</div>` 之后加:

```tsx
                            {canCurate && (
                              <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
                                <button className="btn btn-ghost btn-sm" onClick={() => doUpdateExhibit(ex.id, ex.title)} disabled={busy}>改</button>
                                <button className="btn btn-ghost btn-sm" onClick={() => doDeleteExhibit(ex.id)} disabled={busy}>删</button>
                              </div>
                            )}
```

- [ ] **Step 5: tsc + build**

Run:
```bash
cd frontend && npx tsc --noEmit && npm run build
```
Expected: 0 exit。

- [ ] **Step 6: 手测(推荐)** — `npm run dev`,建一个排期展示,试加/改/删展品 + 从征集导入,确认 UI 正常。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/pages/ActivityDetailPage.tsx
git commit -m "feat(activities-fe): 详情页布展面板（布展 #8/8）

策展人在待开始期可布展:手动加展品、改标题、删展品、从征集勾选作品导入
(复制独立副本)。开放后冻结。两步式导入:选征集→勾作品。"
```

---

## Task 9: 文档 — CONTEXT.md 对齐

**Files:** `CONTEXT.md`(第 31、35 行附近)

- [ ] **Step 1: 改「展示」「展品」条目**

第 31 行(展示)整段改为:

```
**展示 (Exhibition)**：
活动的一种类型——策展型**展品**陈列 + 评分。发起人（策展人，持 `change_activity`）
在**待开始**期间于详情页**布展**：自上传文件加展品、改 / 删展品，或从一个**征集**
勾选任意作品导入（复制成独立展品快照）。开放后展品冻结。每名已验证成员可对每个
展品**点赞 / 点踩**（三态：none / like / dislike，互斥、可改可撤、记名）。可选启用
**活动级投票**（复用众议机制：每展品一选项 + K 选），与点赞独立并列。
_Avoid_: 比赛、评选（展示是陈列+点赞，非评奖排名）
```

第 35 行(展品)整段改为:

```
**展品 (Exhibit)**：
展示活动里的一个陈列单元，由一束文件（图片/视频/文档）组成；图片/视频内联渲染。
来源：策展人在待开始（布展）期自上传，或从某征集勾选作品复制而来（快照，独立于
原作品）。开放后冻结。每个展品独立计点赞/点踩；启用投票时同时是一个投票选项。
区别于「作品 Submission」（后者是征集里的投稿）。
_Avoid_: 作品（专指征集的 Submission）
```

- [ ] **Step 2: 提交**

```bash
git add CONTEXT.md
git commit -m "docs: CONTEXT.md 展示/展品条目对齐详情页布展新行为"
```

---

## 自检(plan vs spec 覆盖)

| spec 要求 | 覆盖 task |
|---|---|
| 创建表单删展品栏 | T7 |
| 0 展品可创建 | T5(翻转 JSON 路径) |
| 详情页手动加展品 | T2 + T8 |
| 详情页改展品(标题+整体覆盖文件) | T3B + T8 |
| 详情页删展品 | T3A + T8 |
| 从征集导入(任意作品勾选) | T4 + T8 |
| 复制独立副本 | T4(`test_import_is_independent_snapshot`) |
| 仅待开始(scheduled)可管 | T2/T3/T4 状态门禁(`can_edit`) |
| 门禁 can_change_activity | T2 `get_permissions` |
| 改标题同步 VoteOption.text | T3B |
| 启用投票时加/导入建选项 | T1 helper + T2/T4 |
| CONTEXT.md 对齐 | T9 |

**每个 task 提交时测试全绿**(任务排序保证了这一点:T1-T4 不碰创建路径;T5 是唯一同时改创建+迁移测试的合并点,合并后即绿)。
**无占位符**(所有代码块完整)。
**类型一致**(`_build_exhibit(activity, title, files, voting_enabled)` 在 T1 定义、T2/T4 调用一致;前端 `addExhibit/updateExhibit/deleteExhibit/importFromCollection` 在 T7 定义、T8 调用一致)。

---

## 收尾

全部 task 完成后:
- 后端 `uv run python manage.py test` 全绿
- 前端 `npx tsc --noEmit` + `npm run build` 通过
- T6 的 /code-review 已做
- 按 ready-for-agent 工作流:本计划对应新 issue(实现前可补开 #57 等),实现完 → close
