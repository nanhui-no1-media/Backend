# Cobalt 设计底座 + 任务/活动详情页对齐 — 设计规格

- 日期: 2026-07-14
- 状态: 已批准（方案 A）
- 来源设计: Open Design 项目 `4bd1d67c-2d83-4ad1-8b59-f92f3f5c521c`（cobalt 主题原型）

## 1. 背景与目标

存在两套产物：

- **Open Design 原型（目标设计）**：完整的 "cobalt" 设计系统（`css/cobalt.css`），含设计令牌（`--brand-900…50` 钴蓝色阶、`--ink-*`、状态色、Sora+PingFang 字体、4px 间距、圆角/阴影刻度、`--nav-h:64px`、`--container:1200px`）与可复用组件类（`.topnav`、`.btn`、`.card`、`.badge`、`.chip`、`.field`、`.alert`、`.modal`、`.seg`、`.page-head`、`.breadcrumb`、`.avatar`、`.footer` 等）。登录态由 `body.is-authed` 驱动。页面有 home / news / news-detail / activity（活动申报+意见反馈）/ tasks（列表/时间线/甘特），但**没有详情页**。
- **现有 `E:\Backend` 应用（当前实现）**：Django + React 19 + TS + Webpack 5。功能成熟但视觉为旧设计。路由已正确映射：`/activity`→proposals、`/activity/:id`→proposal 详情、`/tasks/:id`→task 详情。`TaskDetailPage`、`ProposalDetailPage` **功能完整**（claim / approve / complete / vote / approve-return-reject / 附件 / 讨论全部接线），但使用各页自带的临时 CSS，**不属于 cobalt 系统**，且**不渲染统一顶栏/页脚**（仅一个返回按钮）。无共享 AppShell 组件。后端无 `news` 应用。

本轮目标：落地 cobalt 设计底座，并按新设计重做**任务详情页**与**活动（申报）详情页**两个页面，对齐主题颜色。其余页面维持现状，后续阶段迁移。

## 2. 本轮范围（In Scope）

1. cobalt 设计令牌与全局样式落地。
2. 共享 AppShell（顶栏 + 页脚 + 登录态）。
3. TaskDetailPage 重做为 cobalt（含 AppShell）。
4. ProposalDetailPage（活动详情）重做为 cobalt（含 AppShell）。
5. 主题颜色对齐：用 cobalt 徽章/圆点类替换内联十六进制颜色。

## 3. 不在本轮范围（Out of Scope / 后续阶段）

- 首页、任务列表、活动列表、各表单、站内通信、个人中心等页面的 cobalt 迁移。
- 新闻模块（前端 + Django 后端的新模型/接口/admin）。
- 社团动态卡片（首页）。
- 真实通知中心后端（铃铛未读数若需新端点）。

> 已知并接受的中间态：AppShell 本轮只用于两个详情页，首页/列表页仍为旧顶栏。详情页→顶栏跳转到这些旧页面可用，仅视觉不一致。

## 4. 方案：cobalt 如何进入 React 应用（方案 A）

- 将原型 `css/cobalt.css` **逐字**复制为 `frontend/src/styles/cobalt.css`，在 `frontend/src/index.tsx` 顶部 `import "./styles/cobalt.css"`。Webpack 使用 `style-loader`+`css-loader`，会将其注入为全局样式。所有页面可直接使用原型的真实类名与 CSS 变量，**与原型像素级一致，零漂移**。
- 页面专属规则（`.prio-dot`、`.votebar`、meta 栅格、附件/评论列表等）放入各页 CSS，使用 cobalt 令牌。
- 否决方案 B（仅令牌 + 手写所有组件）：工作量大、必然与原型漂移。
- 字体：保留 cobalt.css 顶部的 Google Fonts `@import`（Sora + Noto Sans SC）；运行期联网加载，开发态可接受。

## 5. 底座交付物（Foundation）

### 5.1 全局样式
- 新建 `frontend/src/styles/cobalt.css`（原型 verbatim）。
- `frontend/src/index.tsx` 顶部引入。

### 5.2 共享 AppShell
- 新建 `frontend/src/components/AppShell.tsx` + `frontend/src/components/AppShell.css`。
- 结构：`<TopNav/>` + `<main>{children}</main>` + `<Footer/>`。
- **TopNav**（sticky `--nav-h`）：
  - brand：「传媒社 · 南汇一中 · 2026」（修正现有 "传媒设" 错字）。
  - 主导航：`主页(/) / 活动申报(/activity) / 任务(/tasks)`。**新闻、社团简介、关于网站本轮不放入**（无对应路由，避免死链）。
  - `bell`（站内通信）：点击跳转 `/messages`；若客户端可获取会话列表则汇总 `unread_count` 显示未读点，否则静态红点。
  - 已登录：`user-chip` 下拉（个人中心 / 任务管理 / 活动申报 / 后台管理 / 退出登录）；未登录：`登录` 按钮→`/login`。
  - 移动端抽屉（`<900px`）。
  - 登录态来自 `api.me()`（替代原型的 `body.is-authed`）。
- **Footer**：4 列（品牌 + 栏目 + 社团 + 账户）+ © 行。

### 5.3 资源与模板
- 复制原型 `assets/favicon.ico`、`assets/wave-mark.svg` 到 `frontend/public/`。
- 修正 `frontend/template.html`：标题改「传媒社」、`lang="zh-CN"`、加 favicon link。

## 6. Task Detail 页面（cobalt，功能保持）

外层包裹 `AppShell`。结构：

- **面包屑** `主页 / 任务 / {title}` + **page-head**：状态徽章 + `<h1>` + 副标题（优先级圆点 · 创建人 · 负责人 · 创建时间）+ 操作按钮（编辑[仅 pending] / 提交验收 / 通过验收 / 打回 / 取消任务）。
- **打回提示**：`task.status==="in_progress" && task.reject_reason` → `.alert-warning`。
- **Meta 卡片**：优先级圆点（`.prio-dot` 映射见 §7）、创建人/负责人头像、时间戳。
- **区块**（cobalt `.card`）：描述（RichTextEditor 只读）· 认领任务（textarea+按钮，`canClaim` 时）· 认领请求审批列表（创建人/社长）· 协作者 · 标签 · 附件（上传/删除）· 讨论（消息列表 + `@mention` 输入）。
- **保留全部既有 handler**：claim / approveClaim / rejectClaim / complete / approveCompletion / rejectCompletion / cancel / addAttachment / deleteAttachment / sendMessage。仅改动标记与 className。

## 7. Activity/Proposal Detail 页面（cobalt，功能保持）

外层包裹 `AppShell`。结构：

- **面包屑** `主页 / 活动申报 / {title}` + **page-head**：状态徽章 + `<h1>` + 副标题（类型 · 申报人/匿名 · 日期）+ 操作（重新提交 / 撤回 / 通过 / 打回 / 拒绝 / 编辑）。
- **打回/拒绝提示**：`.alert-danger`。
- **Meta 卡片**：activity_type / 申报人 / 拟办日期 / 地点 / 预计人数 / 预算 / 提交时间 / 审核人；反馈类型则为 类别 / 匿名 / 联系方式（仅社长可见）。
- **详细说明**（RichTextEditor）。
- **投票区**（仅 activity）：复用原型 `.vote-deadline / .vote-summary / .votebar / .vote-num / .vote-actions / .vote-list`。三色条（赞成 success / 反对 danger / 弃权 line-2），汇总数，投票按钮，投票人列表。
- **附件** + **讨论**（仅 activity）。
- **保留全部既有 handler**：vote / approve / returnProposal / reject / resubmit / withdraw / addAttachment / deleteAttachment / sendMessage。

## 8. 主题颜色对齐（替换内联 hex）

用 cobalt 徽章/圆点类替换 `STATUS_COLORS / PRIORITY_COLORS / PROPOSAL_STATUS_COLORS / VOTE_CHOICE_COLORS` 的内联十六进制用法：

- Task 状态徽章：pending→neutral，in_progress→brand，reviewing→warning，review→brand，completed→success，cancelled→neutral。
- Proposal 状态徽章：voting→brand，pending_approval→warning，returned→danger，approved→success，rejected→neutral，withdrawn→neutral。
- 优先级圆点：urgent→`--danger`，high→`--warning`，medium→`--brand-500`，low→`--ink-400`。
- 投票：approve→success，oppose→danger，abstain→faint。

## 9. 后端

**本轮无需后端改动** — 两个详情页所需全部字段与动作已存在于 `tasks/` 与 `proposals/` 接口（已核实）。新闻模块与真实通知中心端点属后续阶段。

## 10. 文件清单

新建：
- `frontend/src/styles/cobalt.css`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/AppShell.css`

修改：
- `frontend/src/index.tsx`（引入 cobalt.css）
- `frontend/template.html`（标题/语言/favicon）
- `frontend/src/pages/TaskDetailPage.tsx` + `frontend/src/pages/TaskDetailPage.css`
- `frontend/src/pages/ProposalDetailPage.tsx` + `frontend/src/pages/Proposals.css`

资源：
- `frontend/public/favicon.ico`、`frontend/public/wave-mark.svg`（复制自原型）

## 11. 运行 / 预览 / 验证

```bash
# 后端
uv run python manage.py runserver          # :8000
# 前端
cd frontend && npm run dev                 # :3000（API 代理到 :8000）
# 类型/构建自检
cd frontend && npm run build
# 登录后访问详情页（hash 路由）：
#   http://localhost:3000/#/tasks/<id>
#   http://localhost:3000/#/activity/<id>
```

验收要点：两详情页出现统一 cobalt 顶栏/页脚；状态徽章/优先级圆点/投票条采用 cobalt 配色；全部既有操作（认领、验收、投票、审批、附件、讨论）可正常工作；品牌名显示「传媒社」。
