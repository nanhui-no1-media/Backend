# 首页「社团动态」聚合 Feed — 设计文档

- **日期**: 2026-07-20
- **作者**: brainstorming session (jinha + Claude)
- **状态**: 待评审
- **范围**: 首页 `HomePage.tsx` 的「社团动态」区，用真实数据替换当前 mock

---

## 1. 目标

把首页「社团动态」区从硬编码 mock（`HomePage.tsx` 里的 `ACTIVITIES` 数组，注释标为"后续债"）替换成**真实数据**，内容来自三个板块：

- **活动** = 已通过的「活动申报」(`Proposal`, `proposal_type="activity"`, `status="approved"`)
- **任务** = 进行中的 `Task`
- **新闻** = 已发布 `News` (`is_published=True`)

呈现要**多种多样**：不同内容类型用不同卡片形态，并按"头条 + 便当格"混排大小不一的格子。

## 2. 非目标（范围之外）

- 不改首页 Hero、左侧看板娘栏、社团概览、快速入口（只换右栏「社团动态」内容）。
- 不做统一的 `/feed` 列表页（"全部动态"暂指 `/news`）。未来可加。
- 不做"加载更多 / 分页"；首页固定取一批（`limit`，默认 6 条 + 头条）。
- 不动三个板块各自的列表页 / 详情页。
- 不引入新的前端测试框架（仓库目前只有 Django 测试 + TS 类型检查）。

## 3. 已确认决策（来自 brainstorming）

| 决策点 | 选择 |
|---|---|
| 整体结构 | **C · 头条 + 便当格**（精选新闻大卡 + 大小不一的便当格混排） |
| 可见性 | **B · 游客看 活动 + 新闻；任务仅登录成员可见** |
| 后端落点 | 放在 **news app**（与已有 `overview()` 一致），不做新 app |
| 数据来源 | 新建后端聚合接口（见下） |

## 4. 现状与关键约束

当前三个板块的匿名可见性（已核实 `views.py` 权限）：

| 板块 | 匿名可读？ | 权限 |
|---|---|---|
| 新闻 `News` | ✅ 是 | `DjangoModelPermissionsOrAnonReadOnly`（公开 action 匿名可读） |
| 活动 `Proposal` | ❌ 否 | `IsAuthenticated` + `CanViewProposal` |
| 任务 `Task` | ❌ 否 | `IsAuthenticated` + `CanViewTask` |

**推论**：要实现 B（游客可见活动），现有接口做不到——除非把申报接口整体开放给匿名，那会把 `budget` / `vote_summary` / `reject_reason` / `contact` 等内部字段一并暴露。因此**必须有一个聚合接口**，由服务端只投影活动的公开字段。

## 5. 架构：后端聚合接口

### 5.1 选择：`GET /news/feed/`（NewsViewSet 的新 action）

在 `news/views.py` 的 `NewsViewSet` 上加一个 `@action(detail=False, methods=["get"])` 名为 `feed`，并把 `"feed"` 加入 `PUBLIC_ACTIONS`（匿名可读）。与已有的 `featured` / `hot` / `overview` 完全同构。

为可测试与隔离，把组装逻辑抽到独立 helper：`news/feed.py` 的 `build_feed(*, user, limit) -> dict`。view 只做参数解析 + 调用 + 返回。

### 5.2 为什么不做"前端分别请求三接口再合并"

- 活动 / 任务接口都要登录，**游客根本拿不到数据**；要拿到就得把内部字段也开放，违反 B 的隐私要求。
- "任务对外不可见"必须在服务端强制；前端"藏"会被网络面板绕过（对登录用户也存在合并/排序/去重逻辑散落、三次请求等问题）。
- 聚合接口顺带统一了排序、去重、类型打散、可见性——集中、可测。

## 6. 接口规格

```
GET /news/feed/?limit=6
```

- `limit`：返回 `items` 条数上限，默认 6，最大 20。
- 匿名可读；登录用户多返回任务条目。

**响应**：

```jsonc
{
  "featured": { /* NewsFeedItem | null */ },
  "items":    [ /* FeedItem[]，最多 limit 条，已排序+打散，不含 featured */ ]
}
```

- `featured`：头条 = 新闻（选取规则同现有 `featured()` action：`featured=True` 优先，否则按 `views` 降序）。无任何新闻时为 `null`。
- `items`：混排的活动 / 新闻 /（登录时的）任务，**不含** `featured` 那条新闻。

## 7. 数据模型：统一 FeedItem

TypeScript 判别联合（将放在 `frontend/src/types/feed.ts`；后端按同样形状产出 dict）：

```ts
type FeedType = "news" | "activity" | "task";

interface FeedItemBase {
  type: FeedType;
  id: number;
  title: string;
  timestamp: string;   // ISO8601，排序依据，兼供调试
  // 不含 url：SPA 路由由前端按 type+id 自行映射（后端不耦合前端路由）
}

// 新闻（带封面）
interface NewsFeedItem extends FeedItemBase {
  type: "news";
  category: "notice" | "recap" | "work" | "inform";
  summary: string;
  cover_image_url: string | null;
  views: number;
}

// 活动 = 已通过 Proposal 的【公开投影】（仅以下字段）
interface ActivityFeedItem extends FeedItemBase {
  type: "activity";
  activity_type: "competition" | "training" | "project" | "sharing" | "event";
  phase: "upcoming" | "ongoing" | "ended" | null;  // 由 planned_date 推导
  planned_date: string | null;     // ISO date
  location: string;
  expected_participants: number | null;
}

// 任务（仅登录成员）
interface TaskFeedItem extends FeedItemBase {
  type: "task";
  status: "pending" | "in_progress" | "reviewing" | "review";
  priority: "low" | "medium" | "high" | "urgent";
  assignee: { id: number; username: string; nickname: string; avatar: string | null } | null;
}

type FeedItem = NewsFeedItem | ActivityFeedItem | TaskFeedItem;
interface FeedResponse { featured: NewsFeedItem | null; items: FeedItem[]; }
```

**活动公开投影的安全保证**：服务端**只**取 `title / activity_type / planned_date / location / expected_participants / approved_at(或 created_at)`。**绝不**包含 `budget / vote_summary / reject_reason / contact / creator` 等内部字段——既对游客，也对成员（卡片用不到这些）。

**活动 `phase` 推导**（`planned_date` 为 DateField）：
- `> 今天` → `upcoming`（即将开始）
- `== 今天` → `ongoing`（进行中）
- `< 今天` → `ended`（已结束）
- `null` → `null`

## 8. 选材与排序算法（`build_feed`）

1. **头条** `featured`：`News.objects.filter(is_published=True)`，`featured=True` 优先；否则 `order_by("-views","-published_at","-created_at")` 第一条。无则 `null`。该条从候选 `items` 中排除。
2. **候选条目**（各带 `timestamp` 用于排序）：
   - 新闻：已发布、排除头条 → `timestamp = published_at`（回退 `created_at`）
   - 活动：`proposal_type="activity" AND status="approved"` → `timestamp = approved_at`（回退 `created_at`）
   - 任务：**仅当 `user.is_authenticated`**，`status in (pending, in_progress, reviewing, review)`（即未完结、未取消）→ `timestamp = updated_at`
3. **排序**：按 `timestamp` 降序。
4. **类型打散**：轻量 O(n) 处理——若出现连续 3 条同类型，把第 3 条与后续最近的一条异类型交换。保留近似时间序。
5. **截断**：取前 `limit` 条作为 `items`。

> 任务可见性细节：MVP 用"未完结任务"作为成员可见的活跃子集。实现时需确认与 `CanViewTask` 一致（某成员依 `CanViewTask` 看不到的任务不应出现在其 feed 中）——列入实现计划核实项；若 `CanViewTask` 有额外过滤，复用其 queryset 逻辑。

## 9. 可见性矩阵

| 访客 | `featured` | `items` 含 |
|---|---|---|
| 匿名 | 新闻（或 null） | 新闻 + 活动 |
| 登录成员 | 新闻（或 null） | 新闻 + 活动 + 任务 |

可见性由服务端在 `build_feed` 里按 `user.is_authenticated` 强制。

## 10. 前端

### 10.1 组件

```
pages/HomePage.tsx                 // 拉 newsApi.feed()，渲染 <ClubFeed/>（替换 mock）
components/ClubFeed.tsx            // 容器：头条 + 便当格；按 type 分派卡片；空/加载态
components/feed/FeaturedNewsCard.tsx
components/feed/NewsFeedCard.tsx
components/feed/ActivityFeedCard.tsx
components/feed/TaskFeedCard.tsx
```

`ClubFeed` 按 `items` 的**位置**决定格子尺寸（与内容类型解耦，布局稳定）：

| 位置 | 格子 | 说明 |
|---|---|---|
| `items[0]` | 大格（`grid-column: span 2`，较高） | 任意类型都能落位 |
| `items[1]` | 中格（`span 1`，较高；新闻则有封面） | |
| `items[2..]` | 小格（`span 1`） | |

- 头条（`featured`）在便当格上方，整行宽。
- 卡片**内部**按 `type` 不同：新闻=封面+分类+标题；活动=暖色块+类型 emoji+分类徽章+日期/地点/人数+`phase`；任务=状态胶囊+优先级条形+标题+负责人。
- 响应式：窄屏便当格列数收缩（CSS `grid-template-columns: repeat(auto-fit, minmax(...))`）。
- 类型↔图标/配色映射（活动）：`competition`📷 `training`🎬 `project`🎥 `sharing`💡 `event`🎉；配色与 brainstorm mockup 一致（新闻=紫、活动=琥珀、任务=蓝）。

### 10.2 类型与 API

- 新增 `frontend/src/types/feed.ts`：上述 `FeedItem` 联合 + `FeedResponse`。
- 在 `frontend/src/api/news.ts` 的 `newsApi` 加一项（与 `featured/hot/overview` 同构）：
  ```ts
  feed: (limit = 6) => request(`/news/feed/?limit=${limit}`) as Promise<FeedResponse>;
  ```

### 10.3 样式

- 扩展 `frontend/src/styles/home.css`，遵循 cobalt 的 `.cs` 作用域约定（见记忆 `cobalt-design-migration`），不制造全局泄漏。

## 11. 导航（点击去向）

| 卡片 | 去向 | 匿名 |
|---|---|---|
| 新闻 | `/news/:id` | 直接可读 |
| 活动 | `/activity/:id`（= ProposalDetailPage） | 走现有 `go()` → 弹登录（引流，不白送内部信息） |
| 任务 | `/tasks/:id` | 任务卡本身仅成员可见，不存在匿名点击 |
| "全部动态" | `/news` | 暂时（统一 `/feed` 列表页为未来项） |

> 路由由前端按 `type + id` 映射；实现时核对 `App.tsx` 的实际路由path（活动详情 SPA 路径 `/activity/:id` 与 API 路径 `/proposals/:id/` 不同，故必须前端映射）。

## 12. 空 / 边界状态

- **无任何新闻**：`featured=null`，不渲染头条条；`items` 由活动（+成员任务）组成。
- **无已通过活动**：活动格缺席，新闻/任务自然补位（位置式尺寸规则不受影响）。
- **匿名（无任务）**：`items` 仅新闻+活动，格位照常。
- **全空**：渲染一句轻量空状态（如"暂无动态"）。
- **接口失败**：`ClubFeed` 捕获错误，静默退化为空状态（不阻塞首页其余部分；首页其他区块独立）。

## 13. 测试

后端（Django test runner，主力自动覆盖）——`news/tests/`（或 `test_feed.py`）针对 `build_feed`：

- 匿名用户：`items` 含新闻+活动，**不含**任务；`featured` 选取正确。
- 登录用户：`items` 含任务（且为未完结）。
- 排序：按 `timestamp` 降序。
- 类型打散：构造连续 3 同类型，断言被交换。
- 活动**公开投影**：断言响应里不含 `budget / vote_summary / reject_reason / contact / creator`。
- 空状态：无新闻/无活动/全空 各场景。
- `limit` 上限裁剪。

前端：TS 类型（`FeedItem` 联合）保证分派安全；无 JS 测试框架，靠类型 + 手动验证（匿名 vs 登录两种态、各卡片类型、空态）。

## 14. 文件改动清单

**后端**
- `news/feed.py`（新）：`build_feed(*, user, limit) -> dict`（纯函数，可单测）。
- `news/views.py`：`NewsViewSet` 加 `feed()` action；`PUBLIC_ACTIONS` 加 `"feed"`。
- `news/tests/test_feed.py`（新）：上述测试。

**前端**
- `frontend/src/types/feed.ts`（新）：`FeedItem` / `FeedResponse`。
- `frontend/src/api/news.ts`：`newsApi.feed()`。
- `frontend/src/components/ClubFeed.tsx`（新）+ `frontend/src/components/feed/*.tsx`（新）。
- `frontend/src/pages/HomePage.tsx`：删除 `ACTIVITIES` mock 与本地 `Activity` 接口，改用 `<ClubFeed/>`。
- `frontend/src/styles/home.css`：便当格 + 各卡片样式（cobalt `.cs` 作用域）。

**无 model 改动、无 migration。**

## 15. 未来（不在本期）

- 统一 `/feed` 列表页 + 分页 / "加载更多"。
- 按类型筛选 feed。
- 头条轮播（多条 featured）。
- feed 结果级缓存（公共、低频变更，可短期缓存）。
