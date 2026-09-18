import { NavLink } from "react-router-dom";

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

const TABS = [
  {
    to: "/m",
    label: "首页",
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M3 10.5 12 3l9 7.5" />
        <path d="M5 9.5V21h14V9.5" />
      </svg>
    ),
  },
  {
    to: "/m/activity",
    label: "活动",
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M8 3v4M16 3v4M3 10h18" />
      </svg>
    ),
  },
  {
    to: "/m/news",
    label: "新闻",
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M4 5h13v14H4z" />
        <path d="M17 8h3v9a2 2 0 0 1-2 2H4" />
        <path d="M7 9h7M7 12h7M7 15h4" />
      </svg>
    ),
  },
  {
    to: "/m/me",
    label: "我的",
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
      </svg>
    ),
  },
];

/** 手机版底部 tab 栏（固定在视口底部，含安全区）。 */
export default function MobileTabBar() {
  return (
    <nav className="m-tabbar">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.to === "/m"}
          className={({ isActive }) => "m-tab" + (isActive ? " active" : "")}
        >
          {t.icon}
          <span>{t.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
