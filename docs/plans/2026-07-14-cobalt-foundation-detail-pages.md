# Cobalt 底座 + 任务/活动详情页 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Open Design 原型的 cobalt 设计系统落地到现有 React 应用，并按新设计重做「任务详情页」与「活动（申报）详情页」，对齐主题颜色，功能保持不变。

**Architecture:** 全局引入 cobalt 设计令牌与组件类（仅把通用 reset 限定在 `.cs` 包裹下，避免波及未迁移的旧页面）；新增共享 `AppShell`（顶栏+页脚+登录态）与共享 `detail.css` 详情页基元；两个详情页包裹在 `AppShell` 内，用 cobalt 类重写 JSX，保留全部既有 handler 与状态逻辑。

**Tech Stack:** React 19 + TypeScript + Webpack 5（`style-loader`+`css-loader`），Django 6.0 后端（本轮不改）。Hash 路由。

**Testing note（重要）：** 本仓库**前端无单元测试设施**（无 `*.test.tsx`、无 jest/vitest 配置）。前端改动的自动化门禁为 `npm run build`（ts-loader 默认做完整类型检查 + webpack 构建）。视觉与交互正确性通过 dev server + 浏览器人工验证（Playwright MCP 可用于截图核对）。本计划遵循该既有模式，**不伪造前端单测**。后端本轮零改动，故不涉及后端测试。

**Pre-flight（开始前执行一次）:**
- [ ] 在默认分支上先切出特性分支再提交：
```bash
cd E:/Backend
git checkout -b cobalt/detail-pages
```

---

## File Structure

**Create:**
- `frontend/src/styles/cobalt.css` — 原型 cobalt.css **逐字**复制；唯一改动：把通用 reset 限定到 `.cs` 作用域（见 Task 1）。设计系统单一真源。
- `frontend/src/styles/detail.css` — 任务/活动详情页共享的 cobalt 基元（页头行、区块卡、prio-dot、投票条、meta 栅格、附件/评论列表等）。两个详情页共同 import。
- `frontend/src/components/AppShell.tsx` — 共享外壳：sticky 顶栏（品牌+主导航+铃铛+用户菜单/登录+移动抽屉）+ `<main>` + 页脚。登录态来自 `api.me()`，并用 `body.is-authed` 驱动 cobalt 的显隐规则。
- `frontend/src/components/AppShell.css` — 页脚样式（cobalt.css 无 `.footer`）+ flex 布局胶水。
- `frontend/public/wave-mark.svg` — 复制自原型（供后续首页看板娘使用；本轮不引用，预留）。

**Modify:**
- `frontend/src/index.tsx` — 顶部 `import "./styles/cobalt.css";`
- `frontend/template.html` — 标题改「传媒社」、`lang="zh-CN"`、加 favicon。
- `frontend/src/components/Avatar.css` — `.avatar` 渐变改 cobalt 蓝（消除珊瑚色旧主题 + 与 cobalt 的 `.avatar` 对齐）。
- `frontend/src/types/tasks.ts` — 新增 `STATUS_BADGE_CLASS`、`PRIORITY_DOT_CLASS`（保留旧 `*_COLORS` 供列表页使用）。
- `frontend/src/types/proposals.ts` — 新增 `PROPOSAL_STATUS_BADGE_CLASS`。
- `frontend/src/pages/TaskDetailPage.tsx` — import `detail.css`；重写 `return (...)` 为 cobalt 结构并包裹 `AppShell`；其余 state/effect/handler 原样保留。
- `frontend/src/pages/ProposalDetailPage.tsx` — import `detail.css`；重写 `return (...)` 为 cobalt 结构并包裹 `AppShell`；新增 `pct()` 小工具；其余原样保留。

**Unreferenced after（无需删除，留作无害死文件）:**
- `frontend/src/pages/TaskDetailPage.css` — 不再被 import（详情样式迁入 `detail.css`）。

---

## Task 1: Foundation — cobalt 全局样式 + 资源 + 模板

**Files:**
- Create: `frontend/src/styles/cobalt.css`
- Modify: `frontend/src/index.tsx`
- Modify: `frontend/template.html`
- Create: `frontend/public/wave-mark.svg`

- [ ] **Step 1: 复制原型 cobalt.css**

把原型文件逐字复制为 `frontend/src/styles/cobalt.css`：

源（逐字读取后写入目标）：
```
C:\Users\jinha\AppData\Roaming\Open Design\namespaces\release-stable-win\data\projects\4bd1d67c-2d83-4ad1-8b59-f92f3f5c521c\css\cobalt.css
```
目标：`E:\Backend\frontend\src\styles\cobalt.css`

- [ ] **Step 2: 把通用 reset 限定到 `.cs` 作用域**

在新建的 `cobalt.css` 中，把这一行（Reset 段第一行）：

```css
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
```

改为：

```css
.cs, .cs *, .cs *::before, .cs *::after { margin: 0; padding: 0; box-sizing: border-box; }
```

> 原因：`:root` 令牌与所有组件类（`.btn`/`.card`/`.topnav`…）保持全局可用且无害（旧页面不使用这些类名）；只有这条 universal reset 会冲击未迁移页面，故仅它在 `.cs` 内生效。`AppShell` 的根 `<div>` 带 `cs` 类，详情页内容都在其内。

- [ ] **Step 3: 全局引入 cobalt.css**

修改 `frontend/src/index.tsx`，顶部加一行 import：

```tsx
import { createRoot } from "react-dom/client";
import "./styles/cobalt.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(<App />);
```

- [ ] **Step 4: 修正模板标题/语言/favicon**

把 `frontend/template.html` 整体替换为：

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" href="/static/favicon.ico" />
    <title>南汇一中 · 传媒社</title>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
```

- [ ] **Step 5: 复制 wave-mark.svg**

把原型 `assets/wave-mark.svg` 复制为 `frontend/public/wave-mark.svg`（本轮不引用，预留给后续首页）。

- [ ] **Step 6: 构建自检**

```bash
cd frontend && npm run build
```
Expected: 构建成功，无 TS 错误（此步尚未有组件使用 cobalt 类，仅验证样式可被打包）。

- [ ] **Step 7: 提交**
```bash
cd E:/Backend
git add frontend/src/styles/cobalt.css frontend/src/index.tsx frontend/template.html frontend/public/wave-mark.svg
git commit -m "feat(frontend): 引入 cobalt 设计系统全局样式"
```

---

## Task 2: 详情页共享样式 detail.css + 主题类映射

**Files:**
- Create: `frontend/src/styles/detail.css`
- Modify: `frontend/src/types/tasks.ts`
- Modify: `frontend/src/types/proposals.ts`

- [ ] **Step 1: 创建 detail.css**

写入 `frontend/src/styles/detail.css`（依赖 cobalt.css 令牌）：

```css
/* detail.css — 任务/活动详情页共享 cobalt 基元 */
.detail-container { max-width: 880px; }
.detail-body { display: flex; flex-direction: column; gap: var(--s-5); padding: var(--s-8) var(--s-6) var(--s-16); }
.page-head .detail-container { padding-top: var(--s-10); }

.detail-head-row { display:flex; align-items:center; justify-content:space-between; gap: var(--s-4); flex-wrap:wrap; }
.detail-head-main { display:flex; align-items:center; gap: var(--s-3); min-width:0; }
.detail-title { font-family: var(--font-display); font-weight:700; font-size: clamp(22px,3vw,30px); line-height:1.2; }
.detail-head-actions { display:flex; gap: var(--s-2); flex-shrink:0; }
.detail-sub { color: var(--muted); font-size:13.5px; margin-top: var(--s-3); }

.detail-actions { display:flex; flex-wrap:wrap; gap: var(--s-2); }
.detail-row { display:flex; gap: var(--s-2); margin-top: var(--s-3); }
.detail-section { display:flex; flex-direction:column; gap: var(--s-3); }
.section-h { font-family: var(--font-display); font-weight:700; font-size:15px; display:flex; align-items:center; gap: var(--s-2); color: var(--fg); }
.section-h::before { content:""; width:3px; height:14px; border-radius: var(--r-pill); background: var(--brand-700); }
.section-head-row { display:flex; align-items:center; justify-content:space-between; gap: var(--s-3); }
.empty-text { color: var(--faint); font-size:14px; }
.plain-text { white-space:pre-wrap; font-size:14.5px; line-height:1.7; color: var(--ink-900); }

/* priority dot（取自原型 tasks.html） */
.prio-dot { width:10px; height:10px; border-radius: var(--r-pill); flex-shrink:0; box-shadow: 0 0 0 3px var(--bg); }
.prio-dot.is-urgent { background: var(--danger); }
.prio-dot.is-high { background: var(--warning); }
.prio-dot.is-medium { background: var(--brand-500); }
.prio-dot.is-low { background: var(--ink-400); }

/* tags & user chips */
.detail-tags { display:flex; flex-wrap:wrap; gap: var(--s-2); }
.tag-mini { display:inline-flex; align-items:center; padding:1px 8px; border-radius: var(--r-xs); font-size:11.5px; background: var(--brand-50); color: var(--brand-700); }
.chip-row { display:flex; flex-wrap:wrap; gap: var(--s-2); }
.user-chip-inline { display:inline-flex; align-items:center; gap:6px; padding:3px 12px 3px 4px; border:1px solid var(--line); border-radius: var(--r-pill); font-size:13px; color: var(--ink-700); background: var(--bg); }

/* meta grid */
.meta-grid { display:grid; grid-template-columns: repeat(2, 1fr); gap: var(--s-3) var(--s-6); }
.meta-cell { display:flex; flex-direction:column; gap:2px; }
.meta-k { font-size:12px; color: var(--faint); }
.meta-v { font-size:14px; color: var(--fg); }
.user-with-avatar { display:inline-flex; align-items:center; gap:6px; }
@media (max-width:640px){ .meta-grid{grid-template-columns:1fr} }

/* 认领请求 */
.claim-list { display:flex; flex-direction:column; gap: var(--s-3); }
.claim-item { border:1px solid var(--line); border-radius: var(--r-md); padding: var(--s-3) var(--s-4); }
.claim-head { display:flex; align-items:center; gap: var(--s-2); }
.claim-head strong { font-size:14px; }
.claim-time { font-size:12px; color: var(--faint); font-family: var(--font-mono); }
.claim-reason { margin-top: var(--s-2); font-size:13.5px; color: var(--ink-700); background: var(--surface-2); border-radius: var(--r-sm); padding: var(--s-2) var(--s-3); }

/* 附件 */
.att-list { display:flex; flex-direction:column; gap: var(--s-2); }
.att-item { display:flex; align-items:center; gap: var(--s-3); padding: var(--s-2) var(--s-3); border:1px solid var(--line); border-radius: var(--r-sm); }
.att-icon { width:38px; height:28px; border-radius: var(--r-xs); display:inline-flex; align-items:center; justify-content:center; font-size:10px; font-weight:700; font-family: var(--font-mono); background: var(--brand-50); color: var(--brand-700); flex-shrink:0; }
.att-name { color: var(--brand-700); font-size:14px; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.att-name:hover { color: var(--brand-800); }
.att-size { font-size:12px; color: var(--faint); font-family: var(--font-mono); }
.att-del { color: var(--faint); width:26px; height:26px; border-radius: var(--r-xs); display:inline-flex; align-items:center; justify-content:center; }
.att-del:hover { color: var(--danger); background: var(--danger-bg); }

/* 讨论 */
.comment-input { display:flex; flex-direction:column; gap: var(--s-2); }
.comment-list { display:flex; flex-direction:column; gap:0; }
.comment-item { padding: var(--s-3) 0; border-top:1px dashed var(--line); }
.comment-item:first-child { border-top:none; }
.comment-head { display:flex; align-items:center; gap: var(--s-2); margin-bottom:6px; }
.comment-head strong { font-size:14px; }
.comment-time { font-size:12px; color: var(--faint); font-family: var(--font-mono); }
.comment-content { font-size:14px; color: var(--ink-900); line-height:1.6; }

/* 投票（活动详情，取自原型 activity.html） */
.vote-deadline { font-size:13px; color: var(--muted); background: var(--bg-soft); border-radius: var(--r-md); padding: var(--s-3) var(--s-4); }
.vote-deadline strong { color: var(--brand-700); }
.votebar { display:flex; height:8px; width:100%; max-width:340px; border-radius: var(--r-pill); overflow:hidden; background: var(--surface-2); }
.votebar i { display:block; height:100%; }
.votebar i.app { background: var(--success); }
.votebar i.opp { background: var(--danger); }
.votebar i.abs { background: var(--line-2); }
.vote-num { display:inline-flex; gap: var(--s-4); font-size:13px; font-family: var(--font-mono); }
.vote-num .app { color: var(--success); } .vote-num .opp { color: var(--danger); } .vote-num .abs { color: var(--faint); }
.vote-actions { display:flex; gap: var(--s-2); flex-wrap:wrap; }
.vote-btn.approve { background: var(--success); color:#fff; }
.vote-btn.oppose { background: var(--danger); color:#fff; }
.vote-btn.abstain { background: var(--surface-2); color: var(--ink-700); border:1px solid var(--line-2); }
.vote-cast-hint { font-size:13.5px; color: var(--ink-700); }
.vote-cast-hint strong { color: var(--brand-700); }
.vote-list { display:flex; flex-direction:column; gap: var(--s-1); border-top:1px dashed var(--line); padding-top: var(--s-3); }
.vote-item { display:flex; align-items:center; gap: var(--s-2); padding: var(--s-1) 0; font-size:13.5px; }
.vote-name { flex:1; min-width:0; color: var(--ink-700); }
.vote-choice { font-size:12px; font-weight:600; padding:1px 8px; border-radius: var(--r-xs); }
.vote-choice.approve { background: var(--success-bg); color: var(--success); }
.vote-choice.oppose { background: var(--danger-bg); color: var(--danger); }
.vote-choice.abstain { background: var(--surface-2); color: var(--faint); }

@media (max-width:640px){ .detail-head-actions{width:100%} }
```

- [ ] **Step 2: tasks.ts 增加类映射**

在 `frontend/src/types/tasks.ts` 末尾追加（**不要删除**既有 `STATUS_COLORS`/`PRIORITY_COLORS`，列表页仍在用）：

```ts
// cobalt 徽章/圆点类（用于详情页；列表页可后续迁移）
export const STATUS_BADGE_CLASS: Record<TaskStatus, string> = {
  pending: "badge-neutral",
  in_progress: "badge-brand",
  reviewing: "badge-warning",
  review: "badge-brand",
  completed: "badge-success",
  cancelled: "badge-neutral",
};

export const PRIORITY_DOT_CLASS: Record<TaskPriority, string> = {
  low: "is-low",
  medium: "is-medium",
  high: "is-high",
  urgent: "is-urgent",
};
```

- [ ] **Step 3: proposals.ts 增加类映射**

在 `frontend/src/types/proposals.ts` 末尾追加：

```ts
// cobalt 徽章类（用于活动详情页）
export const PROPOSAL_STATUS_BADGE_CLASS: Record<ProposalStatus, string> = {
  voting: "badge-brand",
  pending_approval: "badge-warning",
  returned: "badge-danger",
  approved: "badge-success",
  rejected: "badge-neutral",
  withdrawn: "badge-neutral",
};
```

- [ ] **Step 4: 构建自检**
```bash
cd frontend && npm run build
```
Expected: 成功，无 TS 错误。

- [ ] **Step 5: 提交**
```bash
cd E:/Backend
git add frontend/src/styles/detail.css frontend/src/types/tasks.ts frontend/src/types/proposals.ts
git commit -m "feat(frontend): 详情页共享样式 detail.css 与 cobalt 状态映射"
```

---

## Task 3: AppShell（共享顶栏/页脚/登录态）

**Files:**
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/components/AppShell.css`

- [ ] **Step 1: 创建 AppShell.tsx**

写入 `frontend/src/components/AppShell.tsx`：

```tsx
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import "./AppShell.css";

interface AppShellUser {
  id: number;
  username: string;
  email: string;
  is_president?: boolean;
}
interface AppShellProfile {
  nickname?: string;
  avatar?: string | null;
}

const NAV: { label: string; path: string }[] = [
  { label: "主页", path: "/" },
  { label: "活动申报", path: "/activity" },
  { label: "任务", path: "/tasks" },
];
const USER_MENU: { label: string; path: string }[] = [
  { label: "个人中心", path: "/profile" },
  { label: "任务管理", path: "/tasks" },
  { label: "活动申报", path: "/activity" },
  { label: "后台管理", path: "/admin/" },
];

const BellIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z" />
    <path d="M10 19a2 2 0 0 0 4 0" />
  </svg>
);
const Caret = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9l6 6 6-6" />
  </svg>
);

export default function AppShell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<AppShellUser | null>(null);
  const [profile, setProfile] = useState<AppShellProfile>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const userWrap = useRef<HTMLDivElement>(null);
  const bellWrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.me()
      .then((d: any) => {
        setUser(d.user);
        setProfile(d.profile ?? {});
      })
      .catch(() => setUser(null));
  }, []);

  // 用 body.is-authed 驱动 cobalt 的 .act-guest/.act-user 显隐
  useEffect(() => {
    document.body.classList.toggle("is-authed", !!user);
    return () => { document.body.classList.remove("is-authed"); };
  }, [user]);

  // 点击外部关闭下拉
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (userWrap.current && !userWrap.current.contains(t)) setUserOpen(false);
      if (bellWrap.current && !bellWrap.current.contains(t)) setBellOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const go = (path: string) => {
    setDrawerOpen(false); setUserOpen(false); setBellOpen(false);
    if (path.startsWith("http") || path.endsWith("/")) window.location.href = path;
    else navigate(path);
  };
  const isActive = (p: string) =>
    p === "/" ? location.pathname === "/" : location.pathname.startsWith(p);
  const logout = async () => {
    try { await api.logout(); } finally { navigate("/login"); }
  };
  const name = profile.nickname || user?.username || "";
  const initial = (user?.username || "?").charAt(0).toUpperCase();

  return (
    <div className="cs appshell">
      <header className={"topnav" + (drawerOpen ? " is-open" : "")}>
        <div className="topnav-inner">
          <a className="topnav-brand" role="button" tabIndex={0} onClick={() => go("/")} aria-label="传媒社 首页">
            <img src="/static/favicon.ico" alt="传媒社社徽" />
            <span className="brand-name"><b>传媒社</b><span>南汇一中 · 2026</span></span>
          </a>
          <nav className="topnav-items" aria-label="主导航">
            {NAV.map((n) => (
              <a key={n.path} className="topnav-item" href="#"
                 aria-current={isActive(n.path) ? "page" : undefined}
                 onClick={(e) => { e.preventDefault(); go(n.path); }}>{n.label}</a>
            ))}
          </nav>
          <div className="topnav-actions">
            <div className="act-guest">
              <button className="btn btn-primary btn-sm" onClick={() => go("/login")}>登录</button>
            </div>
            <div className="act-user">
              <div className="bell-wrap" ref={bellWrap}>
                <button className="bell" type="button" aria-label="站内通信"
                        aria-expanded={bellOpen} onClick={() => setBellOpen((v) => !v)}>
                  <BellIcon />
                  <span className="bell-dot" />
                </button>
                {bellOpen && (
                  <div className="bell-panel is-open" role="menu" aria-label="站内通信">
                    <div className="bell-head"><span>站内通信</span></div>
                    <a className="bell-foot" href="#"
                       onClick={(e) => { e.preventDefault(); go("/messages"); }}>查看全部站内通信</a>
                  </div>
                )}
              </div>
              <div className="user-chip-wrap" ref={userWrap}>
                <button className="user-chip" type="button" aria-expanded={userOpen}
                        onClick={() => setUserOpen((v) => !v)}>
                  <span className="avatar">{initial}</span>
                  <span className="uc-name">{name}</span>
                  <Caret className="uc-caret" />
                </button>
                {userOpen && (
                  <div className="user-menu is-open" role="menu">
                    <div className="um-head">
                      <span className="avatar lg">{initial}</span>
                      <div>
                        <div className="um-name">{name}</div>
                        <div className="um-sub">@{user?.username}</div>
                      </div>
                    </div>
                    {USER_MENU.map((m) => (
                      <button key={m.path} className="user-menu-item" type="button" onClick={() => go(m.path)}>
                        {m.label}
                      </button>
                    ))}
                    <div className="um-sep" />
                    <button className="user-menu-item danger" type="button" onClick={logout}>退出登录</button>
                  </div>
                )}
              </div>
            </div>
            <button className="topnav-toggle" type="button" aria-label="打开菜单"
                    aria-expanded={drawerOpen} onClick={() => setDrawerOpen((v) => !v)}>
              <span />
            </button>
          </div>
        </div>

        <div className="mobile-sheet">
          {NAV.map((n) => (
            <a key={n.path} className={isActive(n.path) ? "active" : ""} href="#"
               onClick={(e) => { e.preventDefault(); go(n.path); }}>{n.label}</a>
          ))}
          <div className="sheet-sep" />
          {user ? (
            <>
              <button className="sheet-item" type="button" onClick={() => go("/profile")}>个人中心</button>
              <button className="sheet-item" type="button" onClick={() => go("/tasks")}>任务管理</button>
              <button className="sheet-item" type="button" onClick={() => go("/activity")}>活动申报</button>
              <button className="sheet-item" type="button" onClick={() => go("/messages")}>站内通信</button>
              <button className="sheet-item" type="button" onClick={logout}>退出登录</button>
            </>
          ) : (
            <button className="sheet-item" type="button" onClick={() => go("/login")}>登录</button>
          )}
        </div>
      </header>

      <main className="page">{children}</main>

      <footer className="footer">
        <div className="footer-inner">
          <div>
            <div className="footer-brand">
              <img src="/static/favicon.ico" alt="传媒社社徽" />
              <b>传媒社</b>
            </div>
            <p className="footer-note">
              上海市南汇第一中学 · 传媒社<br />
              校园影像与新媒体作品策展门户<br />
              账户由信息组统一分发
            </p>
          </div>
          <div>
            <h5>栏目</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/"); }}>主页</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/activity"); }}>活动申报</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/tasks"); }}>任务</a>
          </div>
          <div>
            <h5>社团</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/"); }}>社团简介</a>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/"); }}>关于网站</a>
          </div>
          <div>
            <h5>账户</h5>
            <a href="#" onClick={(e) => { e.preventDefault(); go("/login"); }}>登录</a>
          </div>
        </div>
        <div className="footer-bottom tnum">© 2026 上海市南汇第一中学 · 传媒社 · 信息组</div>
      </footer>
    </div>
  );
}
```

- [ ] **Step 2: 创建 AppShell.css（页脚 + 布局胶水）**

写入 `frontend/src/components/AppShell.css`：

```css
/* AppShell — cobalt.css 无 .footer，此处补页脚 + flex 布局胶水 */
.appshell { min-height: 100vh; display: flex; flex-direction: column; }
.appshell .page { flex: 1 0 auto; }

.footer { background: var(--brand-900); color: oklch(1 0 0 / .78); margin-top: var(--s-16); }
.footer-inner { max-width: var(--container); margin: 0 auto; padding: var(--s-16) var(--s-6) var(--s-8); display: grid; grid-template-columns: 1.4fr 1fr 1fr 1fr; gap: var(--s-8); }
.footer h5 { font-family: var(--font-display); color: #fff; font-size: 14px; margin-bottom: var(--s-4); letter-spacing: .02em; }
.footer a { display: block; color: oklch(1 0 0 / .68); font-size: 13px; padding: 4px 0; cursor: pointer; }
.footer a:hover { color: var(--brand-300); }
.footer-brand { display: flex; align-items: center; gap: var(--s-3); margin-bottom: var(--s-4); }
.footer-brand img { width: 36px; height: 36px; border-radius: var(--r-pill); background: #fff; padding: 2px; }
.footer-brand b { font-family: var(--font-display); color: #fff; font-size: 16px; }
.footer-note { font-size: 12px; color: oklch(1 0 0 / .5); line-height: 1.7; }
.footer-bottom { border-top: 1px solid oklch(1 0 0 / .12); padding: var(--s-5) var(--s-6); text-align: center; font-size: 12px; color: oklch(1 0 0 / .45); font-family: var(--font-mono); }
@media (max-width: 1024px) { .footer-inner { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .footer-inner { grid-template-columns: 1fr; gap: var(--s-6); } }
```

- [ ] **Step 3: 构建自检**
```bash
cd frontend && npm run build
```
Expected: 成功（AppShell 尚未被引用，仅验证可编译）。

- [ ] **Step 4: 提交**
```bash
cd E:/Backend
git add frontend/src/components/AppShell.tsx frontend/src/components/AppShell.css
git commit -m "feat(frontend): 新增 cobalt 共享外壳 AppShell（顶栏/页脚/登录态）"
```

---

## Task 4: Avatar 对齐 cobalt 蓝

**Files:**
- Modify: `frontend/src/components/Avatar.css`

- [ ] **Step 1: 把 `.avatar` 渐变改为 cobalt 蓝**

在 `frontend/src/components/Avatar.css` 中，把 `.avatar` 的 `background` 行：

```css
  background: linear-gradient(135deg, var(--brand, #e85d4a), #f4a261);
```

改为：

```css
  background: linear-gradient(135deg, var(--brand-600), var(--brand-400));
```

> 这同时消除了旧的珊瑚色（`--brand` 未定义时的回退），并让头像与 cobalt 一致，全站生效（含旧页面，符合颜色对齐目标）。

- [ ] **Step 2: 构建自检**
```bash
cd frontend && npm run build
```
Expected: 成功。

- [ ] **Step 3: 提交**
```bash
cd E:/Backend
git add frontend/src/components/Avatar.css
git commit -m "style(frontend): 头像渐变对齐 cobalt 蓝（替换旧珊瑚色）"
```

---

## Task 5: TaskDetailPage 重做为 cobalt

**Files:**
- Modify: `frontend/src/pages/TaskDetailPage.tsx`

> **保留不变：** 文件中 `import` 之上的所有内容、全部 `useState`/`useRef`/`useEffect`/`handle*` 处理函数、`formatDate`/`formatSize`、派生变量（`isCreator`/`isPresident`/`canClaim`/`canComplete`/`canReviewCompletion`/`canCancel`/`pendingClaims`）。**只改 import、`return` 之前新增一个 helper、以及整个 `return (...)`。**

- [ ] **Step 1: 调整 import**

在 `frontend/src/pages/TaskDetailPage.tsx` 顶部：
- 删除 `import "./TaskDetailPage.css";`
- 新增 `import AppShell from "../components/AppShell";`
- 新增 `import "../styles/detail.css";`
- 在从 `../types/tasks` 的 import 中追加 `STATUS_BADGE_CLASS, PRIORITY_DOT_CLASS`。

即把：
```tsx
import {
  TaskDetail, Message,
  STATUS_LABELS, PRIORITY_LABELS, PRIORITY_COLORS, STATUS_COLORS,
} from "../types/tasks";
import RichTextEditor from "../components/RichTextEditor";
import Avatar from "../components/Avatar";
import "./TaskDetailPage.css";
```
改为：
```tsx
import {
  TaskDetail, Message,
  STATUS_LABELS, PRIORITY_LABELS, PRIORITY_COLORS, STATUS_COLORS,
  STATUS_BADGE_CLASS, PRIORITY_DOT_CLASS,
} from "../types/tasks";
import RichTextEditor from "../components/RichTextEditor";
import Avatar from "../components/Avatar";
import AppShell from "../components/AppShell";
import "../styles/detail.css";
```

> `PRIORITY_COLORS`/`STATUS_COLORS` 暂保留在 import 中无害；若 TS 报 unused，可从 import 删除它们（本步的 `return` 不再使用）。若删除，确认列表页不依赖本文件导出即可。

- [ ] **Step 2: 用 cobalt 结构重写 return**

把整个 `return (...)`（从 `return (` 到对应 `);`）替换为：

```tsx
  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/tasks"); }}>任务</a>
            <span className="sep">/</span>
            <span>{task.title}</span>
          </nav>
          <div className="detail-head-row">
            <div className="detail-head-main">
              <span className={"prio-dot " + PRIORITY_DOT_CLASS[task.priority]}
                    title={"优先级：" + PRIORITY_LABELS[task.priority]} />
              <h1 className="detail-title">{task.title}</h1>
              <span className={"badge " + STATUS_BADGE_CLASS[task.status]}>
                <span className="badge-dot" />{STATUS_LABELS[task.status]}
              </span>
            </div>
            <div className="detail-head-actions">
              {task.status === "pending" && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/tasks/${task.id}/edit`)}>编辑</button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/tasks")}>返回列表</button>
            </div>
          </div>
          <p className="detail-sub">
            {PRIORITY_LABELS[task.priority]} · 创建人 {task.creator.nickname || task.creator.username}
            {" · 负责人 "}{task.assignee ? (task.assignee.nickname || task.assignee.username) : "未分配"}
            {" · "}{new Date(task.created_at).toLocaleDateString("zh-CN")}
          </p>
        </div>
      </div>

      <div className="container detail-container detail-body">
        {error && <div className="alert alert-danger">{error}</div>}

        {task.status === "in_progress" && task.reject_reason && (
          <div className="alert alert-warning"><b>此任务已被打回：</b>{task.reject_reason}</div>
        )}

        {(canComplete || canReviewCompletion || canCancel) && (
          <div className="detail-actions">
            {canComplete && (
              <button className="btn btn-primary" onClick={handleComplete} disabled={actionLoading}>
                {actionLoading ? "处理中…" : "提交验收"}
              </button>
            )}
            {canReviewCompletion && (
              <>
                <button className="btn btn-primary" onClick={handleApproveCompletion} disabled={actionLoading}>通过验收</button>
                <button className="btn btn-ghost" onClick={() => setShowRejectForm(true)} disabled={actionLoading}>打回</button>
              </>
            )}
            {canCancel && (
              <button className="btn btn-ghost" onClick={handleCancel} disabled={actionLoading}>取消任务</button>
            )}
          </div>
        )}

        {showRejectForm && canReviewCompletion && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">打回理由</h3>
            <textarea className="textarea" value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="说明打回原因，告知负责人需返工的内容..." rows={3} />
            <div className="detail-row">
              <button className="btn btn-primary" onClick={handleRejectCompletion} disabled={actionLoading}>
                {actionLoading ? "处理中…" : "确认打回"}
              </button>
              <button className="btn btn-ghost"
                      onClick={() => { setShowRejectForm(false); setRejectReason(""); }}
                      disabled={actionLoading}>取消</button>
            </div>
          </div>
        )}

        {task.tags.length > 0 && (
          <div className="detail-tags">
            {task.tags.map((t) => (
              <span key={t.id} className="tag-mini" style={{ backgroundColor: t.color + "1a", color: t.color }}>{t.name}</span>
            ))}
          </div>
        )}

        <div className="card card-pad detail-section">
          <h3 className="section-h">描述</h3>
          {task.description ? (
            <RichTextEditor content={task.description} editable={false} />
          ) : (
            <p className="empty-text">暂无描述</p>
          )}
        </div>

        {task.collaborators.length > 0 && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">协作者</h3>
            <div className="chip-row">
              {task.collaborators.map((u) => (
                <span key={u.id} className="user-chip-inline">
                  <Avatar user={u} size="sm" />{u.nickname || u.username}
                </span>
              ))}
            </div>
          </div>
        )}

        {canClaim && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">认领任务</h3>
            <textarea className="textarea" value={claimReason}
                      onChange={(e) => setClaimReason(e.target.value)}
                      placeholder="说明你想认领此任务的理由..." rows={2} />
            <button className="btn btn-primary" onClick={handleClaim} disabled={claiming}>
              {claiming ? "提交中…" : "申请认领"}
            </button>
          </div>
        )}

        {(!!isCreator || isPresident) && pendingClaims.length > 0 && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">认领请求 ({pendingClaims.length})</h3>
            <div className="claim-list">
              {pendingClaims.map((cr) => (
                <div key={cr.id} className="claim-item">
                  <div className="claim-head">
                    <Avatar user={cr.claimant} size="sm" />
                    <strong>{cr.claimant.nickname || cr.claimant.username}</strong>
                    <span className="claim-time">{new Date(cr.created_at).toLocaleString("zh-CN")}</span>
                  </div>
                  {cr.reason && <div className="claim-reason">{cr.reason}</div>}
                  <div className="detail-row">
                    <button className="btn btn-primary btn-sm" onClick={() => handleApproveClaim(cr.id)} disabled={actionLoading}>批准</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => handleRejectClaim(cr.id)} disabled={actionLoading}>拒绝</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="card card-pad detail-section">
          <div className="section-head-row">
            <h3 className="section-h">附件 ({task.attachments.length})</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => fileInputRef.current?.click()}>+ 上传</button>
            <input ref={fileInputRef} type="file" onChange={handleFileUpload} style={{ display: "none" }} />
          </div>
          {task.attachments.length > 0 ? (
            <div className="att-list">
              {task.attachments.map((att) => (
                <div key={att.id} className="att-item">
                  <span className="att-icon">
                    {att.file_type === "image" ? "IMG" : att.file_type === "video" ? "VID" :
                     att.file_type === "document" ? "DOC" : att.file_type === "archive" ? "ZIP" : "FILE"}
                  </span>
                  <a href={att.file_url} target="_blank" rel="noopener noreferrer" className="att-name">{att.file_name}</a>
                  <span className="att-size">{formatSize(att.file_size)}</span>
                  <button className="att-del" onClick={() => handleDeleteAttachment(att.id)} title="删除">✕</button>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">暂无附件</p>
          )}
        </div>

        <div className="card card-pad detail-section">
          <h3 className="section-h">讨论 ({messages.length})</h3>
          {conversationId && (
            <div className="comment-input">
              <textarea className="textarea" value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="输入消息，使用 @用户名 提及他人..." rows={3} />
              <button className="btn btn-primary"
                      onClick={handleSendMessage}
                      disabled={!message.trim() || messageSubmitting}>
                {messageSubmitting ? "发送中…" : "发送"}
              </button>
            </div>
          )}
          {messages.length > 0 ? (
            <div className="comment-list">
              {messages.map((m) => (
                <div key={m.id} className="comment-item">
                  <div className="comment-head">
                    <Avatar user={m.sender} size="md" />
                    <strong>{m.sender.nickname || m.sender.username}</strong>
                    <span className="comment-time">{new Date(m.created_at).toLocaleString("zh-CN")}</span>
                  </div>
                  <div className="comment-content">{m.content}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">暂无讨论</p>
          )}
        </div>
      </div>
    </AppShell>
  );
```

- [ ] **Step 3: 构建自检**
```bash
cd frontend && npm run build
```
Expected: 成功，无 TS 错误（确认未使用的 `PRIORITY_COLORS`/`STATUS_COLORS`/`formatDate` 等若报 unused 则从 import 中移除或保留——ts-loader 默认不因 unused import 报错，除非 `noUnusedLocals` 开启；若开启，移除未用 import）。

- [ ] **Step 4: 视觉验证**
```bash
cd frontend && npm run dev
# 后端另开终端：uv run python manage.py runserver
```
浏览器打开（登录后）`http://localhost:3000/#/tasks/<某个真实任务id>`，确认：
- 顶部出现 cobalt sticky 顶栏（传媒社 / 主页·活动申报·任务 / 铃铛 / 头像菜单），底部出现 cobalt 页脚。
- 面包屑「主页 / 任务 / 标题」；优先级圆点颜色（紧急红/高橙/中蓝/低灰）；状态徽章 cobalt 配色。
- 描述/协作者/认领/认领请求/附件/讨论各区块为 cobalt 卡片；按钮为 cobalt primary/ghost/secondary。
- 可触发：申请认领 / 批准·拒绝认领 / 提交验收 / 通过验收·打回（填理由）/ 取消任务 / 上传·删除附件 / 发送讨论。均无报错。

- [ ] **Step 5: 提交**
```bash
cd E:/Backend
git add frontend/src/pages/TaskDetailPage.tsx
git commit -m "feat(frontend): 任务详情页对齐 cobalt 设计（AppShell+新布局，功能不变）"
```

---

## Task 6: ProposalDetailPage 重做为 cobalt

**Files:**
- Modify: `frontend/src/pages/ProposalDetailPage.tsx`

> **保留不变：** 全部 `useState`/`useRef`/`useEffect`/`handle*`/`submitReason`/`formatSize`/`formatRemaining`、派生变量（`isPresident`/`isCreator`/`isActivity`/`summary`/`canVote`/`canApprove`/`canEdit`/`canResubmit`/`canWithdraw`/`canManageAttachment`）。**只改 import、新增 `pct` helper、以及整个 `return (...)`。**

- [ ] **Step 1: 调整 import**

把：
```tsx
import {
  ProposalDetail,
  VoteChoice,
  ACTIVITY_TYPE_LABELS,
  FEEDBACK_CATEGORY_LABELS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_COLORS,
  VOTE_CHOICE_LABELS,
} from "../types/proposals";
import type { Message } from "../types/tasks";
import Avatar from "../components/Avatar";
import RichTextEditor from "../components/RichTextEditor";
import "./Proposals.css";
```
改为：
```tsx
import {
  ProposalDetail,
  VoteChoice,
  ACTIVITY_TYPE_LABELS,
  FEEDBACK_CATEGORY_LABELS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_COLORS,
  PROPOSAL_STATUS_BADGE_CLASS,
  VOTE_CHOICE_LABELS,
} from "../types/proposals";
import type { Message } from "../types/tasks";
import Avatar from "../components/Avatar";
import RichTextEditor from "../components/RichTextEditor";
import AppShell from "../components/AppShell";
import "../styles/detail.css";
```

> `PROPOSAL_STATUS_COLORS` 若在新 `return` 中未使用且 `noUnusedLocals` 报错，则从 import 中删除。

- [ ] **Step 2: 新增 pct helper**

在 `const summary = { ... };` 之后（`return` 之前）插入：

```tsx
  const pct = (n: number, total: number) => (total > 0 ? Math.round((n / total) * 100) : 0) + "%";
```

- [ ] **Step 3: 用 cobalt 结构重写 return**

把整个 `return (...)` 替换为：

```tsx
  return (
    <AppShell>
      <div className="page-head">
        <div className="container detail-container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/activity"); }}>活动申报</a>
            <span className="sep">/</span>
            <span>{p.title}</span>
          </nav>
          <div className="detail-head-row">
            <div className="detail-head-main">
              <h1 className="detail-title">{p.title}</h1>
              <span className={"badge " + PROPOSAL_STATUS_BADGE_CLASS[p.status]}>
                <span className="badge-dot" />{PROPOSAL_STATUS_LABELS[p.status]}
              </span>
            </div>
            <div className="detail-head-actions">
              {canEdit && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/activity/${p.id}/edit`)}>编辑</button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/activity")}>返回列表</button>
            </div>
          </div>
          <p className="detail-sub">
            {isActivity
              ? (ACTIVITY_TYPE_LABELS[p.activity_type as keyof typeof ACTIVITY_TYPE_LABELS] || "活动")
              : (FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "反馈")}
            {" · "}{isActivity ? "申报人" : "提交人"} {p.creator ? (p.creator.nickname || p.creator.username) : "匿名"}
            {" · "}{new Date(p.created_at).toLocaleDateString("zh-CN")}
            {isActivity && p.status === "voting" && p.voting_end_at ? " · " + formatRemaining(p.voting_end_at) : ""}
          </p>
        </div>
      </div>

      <div className="container detail-container detail-body">
        {error && <div className="alert alert-danger">{error}</div>}

        {(p.status === "returned" || p.status === "rejected") && p.reject_reason && (
          <div className="alert alert-danger">
            <b>{p.status === "returned" ? "已打回" : "已拒绝"}：</b>{p.reject_reason}
          </div>
        )}

        {(canVote || canApprove || canResubmit || canWithdraw) && (
          <div className="detail-actions">
            {canResubmit && (
              <button className="btn btn-primary" onClick={handleResubmit} disabled={actionLoading}>
                {actionLoading ? "处理中…" : "重新提交（开始投票）"}
              </button>
            )}
            {canWithdraw && (
              <button className="btn btn-ghost" onClick={handleWithdraw} disabled={actionLoading}>撤回</button>
            )}
            {canApprove && (
              <>
                <button className="btn btn-primary" onClick={handleApprove} disabled={actionLoading}>
                  {actionLoading ? "处理中…" : "通过"}
                </button>
                <button className="btn btn-ghost" onClick={() => setShowReasonForm("return")} disabled={actionLoading}>打回</button>
                <button className="btn btn-danger" onClick={() => setShowReasonForm("reject")} disabled={actionLoading}>拒绝</button>
              </>
            )}
          </div>
        )}

        {showReasonForm && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">{showReasonForm === "return" ? "打回理由" : "拒绝理由"}</h3>
            <textarea className="textarea" value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder={showReasonForm === "return" ? "说明需要修改的内容..." : "说明拒绝原因..."}
                      rows={3} />
            <div className="detail-row">
              <button className="btn btn-primary" onClick={submitReason} disabled={actionLoading}>
                {actionLoading ? "处理中…" : `确认${showReasonForm === "return" ? "打回" : "拒绝"}`}
              </button>
              <button className="btn btn-ghost"
                      onClick={() => { setShowReasonForm(null); setReason(""); }}
                      disabled={actionLoading}>取消</button>
            </div>
          </div>
        )}

        <div className="card card-pad detail-section">
          <h3 className="section-h">基本信息</h3>
          <div className="meta-grid">
            {isActivity ? (
              <>
                <div className="meta-cell"><span className="meta-k">活动类型</span><span className="meta-v">{ACTIVITY_TYPE_LABELS[p.activity_type as keyof typeof ACTIVITY_TYPE_LABELS] || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">拟办日期</span><span className="meta-v">{p.planned_date || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">地点</span><span className="meta-v">{p.location || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">预计人数</span><span className="meta-v">{p.expected_participants != null ? p.expected_participants : "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">预算</span><span className="meta-v">{p.budget != null ? `¥${p.budget}` : "-"}</span></div>
              </>
            ) : (
              <>
                <div className="meta-cell"><span className="meta-k">反馈类别</span><span className="meta-v">{FEEDBACK_CATEGORY_LABELS[p.feedback_category as keyof typeof FEEDBACK_CATEGORY_LABELS] || "-"}</span></div>
                <div className="meta-cell"><span className="meta-k">提交人</span><span className="meta-v">匿名</span></div>
                {!isActivity && p.contact && isPresident && (
                  <div className="meta-cell"><span className="meta-k">联系方式</span><span className="meta-v">{p.contact}</span></div>
                )}
              </>
            )}
            <div className="meta-cell"><span className="meta-k">提交时间</span><span className="meta-v">{new Date(p.created_at).toLocaleString("zh-CN")}</span></div>
            {p.reviewed_by && (
              <div className="meta-cell">
                <span className="meta-k">审核人</span>
                <span className="meta-v user-with-avatar"><Avatar user={p.reviewed_by} size="sm" />{p.reviewed_by.nickname || p.reviewed_by.username}</span>
              </div>
            )}
          </div>
        </div>

        <div className="card card-pad detail-section">
          <h3 className="section-h">详细说明</h3>
          {p.description ? (
            isActivity ? (
              <RichTextEditor content={p.description} editable={false} />
            ) : (
              <div className="plain-text">{p.description}</div>
            )
          ) : (
            <p className="empty-text">暂无说明</p>
          )}
        </div>

        {isActivity && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">投票</h3>
            <div className="vote-deadline">
              {p.status === "voting"
                ? <>投票进行中，<strong>{formatRemaining(p.voting_end_at)}</strong>（公开实名，每人一次，不可修改；结果仅供参考，社长最终决定）</>
                : <>投票已结束（共 {p.votes.length} 票）</>}
            </div>
            <div className="votebar">
              <i className="app" style={{ width: pct(summary.approve, p.votes.length) }} />
              <i className="opp" style={{ width: pct(summary.oppose, p.votes.length) }} />
              <i className="abs" style={{ width: pct(summary.abstain, p.votes.length) }} />
            </div>
            <div className="vote-num">
              <span className="app">赞成 {summary.approve}</span>
              <span className="opp">反对 {summary.oppose}</span>
              <span className="abs">弃权 {summary.abstain}</span>
            </div>
            {canVote ? (
              <div className="vote-actions">
                <button className="btn vote-btn approve" onClick={() => handleVote("approve")} disabled={actionLoading}>{VOTE_CHOICE_LABELS.approve}</button>
                <button className="btn vote-btn oppose" onClick={() => handleVote("oppose")} disabled={actionLoading}>{VOTE_CHOICE_LABELS.oppose}</button>
                <button className="btn vote-btn abstain" onClick={() => handleVote("abstain")} disabled={actionLoading}>{VOTE_CHOICE_LABELS.abstain}</button>
              </div>
            ) : p.my_vote ? (
              <div className="vote-cast-hint">你已投：<strong>{VOTE_CHOICE_LABELS[p.my_vote]}</strong>（不可修改）</div>
            ) : p.status === "voting" ? (
              <div className="empty-text">登录后可参与投票</div>
            ) : null}
            {p.votes.length > 0 && (
              <div className="vote-list">
                {p.votes.map((v) => (
                  <div key={v.id} className="vote-item">
                    <Avatar user={v.voter} size="sm" />
                    <span className="vote-name">{v.voter.nickname || v.voter.username}</span>
                    <span className={"vote-choice " + v.vote_choice}>{VOTE_CHOICE_LABELS[v.vote_choice]}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {isActivity && (
          <div className="card card-pad detail-section">
            <div className="section-head-row">
              <h3 className="section-h">附件 ({p.attachments.length})</h3>
              {canManageAttachment && (
                <>
                  <button className="btn btn-secondary btn-sm" onClick={() => fileInputRef.current?.click()}>+ 上传</button>
                  <input ref={fileInputRef} type="file" onChange={handleFileUpload} style={{ display: "none" }} />
                </>
              )}
            </div>
            {p.attachments.length > 0 ? (
              <div className="att-list">
                {p.attachments.map((att) => (
                  <div key={att.id} className="att-item">
                    <span className="att-icon">
                      {att.file_type === "image" ? "IMG" : att.file_type === "video" ? "VID" :
                       att.file_type === "document" ? "DOC" : att.file_type === "archive" ? "ZIP" : "FILE"}
                    </span>
                    <a href={att.file_url} target="_blank" rel="noopener noreferrer" className="att-name">{att.file_name}</a>
                    <span className="att-size">{formatSize(att.file_size)}</span>
                    {canManageAttachment && (
                      <button className="att-del" onClick={() => handleDeleteAttachment(att.id)} title="删除">✕</button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-text">暂无附件</p>
            )}
          </div>
        )}

        {isActivity && (
          <div className="card card-pad detail-section">
            <h3 className="section-h">讨论 ({messages.length})</h3>
            {conversationId && (
              <div className="comment-input">
                <textarea className="textarea" value={message}
                          onChange={(e) => setMessage(e.target.value)}
                          placeholder="输入消息，使用 @用户名 提及他人..." rows={3} />
                <button className="btn btn-primary btn-sm"
                        onClick={handleSendMessage}
                        disabled={!message.trim() || messageSending}>
                  {messageSending ? "发送中…" : "发送"}
                </button>
              </div>
            )}
            {messages.length > 0 ? (
              <div className="comment-list">
                {messages.map((m) => (
                  <div key={m.id} className="comment-item">
                    <div className="comment-head">
                      <Avatar user={m.sender} size="md" />
                      <strong>{m.sender.nickname || m.sender.username}</strong>
                      <span className="comment-time">{new Date(m.created_at).toLocaleString("zh-CN")}</span>
                    </div>
                    <div className="comment-content">{m.content}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-text">暂无讨论</p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
```

- [ ] **Step 4: 构建自检**
```bash
cd frontend && npm run build
```
Expected: 成功，无 TS 错误。

- [ ] **Step 5: 视觉验证**
```bash
cd frontend && npm run dev   # 后端另开：uv run python manage.py runserver
```
浏览器打开（登录后）`http://localhost:3000/#/activity/<某个真实活动申报id>`，确认：
- cobalt 顶栏/页脚/面包屑「主页 / 活动申报 / 标题」；状态徽章 cobalt 配色（投票中蓝/待审批橙/已打回红/已通过绿…）。
- 基本信息为 meta 栅格；详细说明渲染；投票区有 cobalt 三色投票条 + 赞成/反对/弃权数 + 投票按钮 + 投票人列表。
- 可触发：投票 / 重新提交 / 撤回 / 通过 / 打回（理由）/ 拒绝（理由）/ 编辑跳转 / 上传·删除附件 / 发送讨论。均无报错。
- 另打开一条「意见反馈」类申报（feedback）确认：无投票/附件/讨论区，显示匿名 + 类别 + 联系方式（社长视角）。

- [ ] **Step 6: 提交**
```bash
cd E:/Backend
git add frontend/src/pages/ProposalDetailPage.tsx
git commit -m "feat(frontend): 活动(申报)详情页对齐 cobalt 设计（AppShell+投票条+新布局，功能不变）"
```

---

## Task 7: 集成回归与旧页面影响核查

**Files:** （只读核查，按需修补）

- [ ] **Step 1: 全量构建**
```bash
cd frontend && npm run build
```
Expected: 成功。

- [ ] **Step 2: 旧页面影响核查（cobalt 全局化的副作用）**

启动 `npm run dev` + 后端，逐一访问并截图/目测，确认未迁移页面**未被破坏**（重点：cobalt 全局 `body` 字体、`a`/`button` 基线、`.cs` 外不受 universal reset 影响）：
- `/#/` 首页（旧设计，应仍正常；仅头像变蓝、链接变 cobalt 蓝）
- `/#/tasks` 任务列表
- `/#/activity` 活动列表
- `/#/messages` 站内通信
- `/#/profile` 个人中心
- `/#/login` 登录页

> 若某旧页面因 cobalt 基线（如 `a{color}`、`button{font:inherit}`）出现明显异常，**记录**但**不在本轮修复**（属于后续迁移阶段），除非属硬性破坏（布局坍塌）——届时用最小补丁在该页 CSS 内覆盖。

- [ ] **Step 3: 详情页跨断点核查**

在 `/#/tasks/<id>` 与 `/#/activity/<id>` 下，缩窄至 ≤640px 与 ≤900px：
- ≤900px：顶栏切换为汉堡抽屉，可展开/收起，导航可用。
- ≤640px：page-head、meta 栅格（单列）、投票按钮换行正常，无横向溢出。

- [ ] **Step 4: 收尾提交（如有点缀修补）**
```bash
cd E:/Backend
git add -A
git commit -m "chore(frontend): cobalt 详情页对齐收尾" || echo "无改动，跳过"
```

---

## 验收要点（Definition of Done）

- [ ] `npm run build` 通过，无 TS 错误。
- [ ] 任务详情页、活动详情页均渲染 cobalt 统一顶栏 + 页脚 + 面包屑 + page-head。
- [ ] 状态徽章/优先级圆点/投票条采用 cobalt 配色（无残留旧 hex 内联色）。
- [ ] 两详情页全部既有操作可用（认领/验收/取消/投票/审批/打回/拒绝/重新提交/撤回/附件/讨论）。
- [ ] 头像为 cobalt 蓝；品牌名显示「传媒社」。
- [ ] 未迁移页面未被破坏（无布局坍塌）。
- [ ] 移动端抽屉与响应式正常。
- [ ] 全部提交位于 `cobalt/detail-pages` 分支。
