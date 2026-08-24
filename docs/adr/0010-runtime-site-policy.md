# 运行时站点策略（DB 单例 knobs vs env 密钥）

日期：2026-08-24 · 与 jinha 协作

## 决策

运营向旋钮（验证通道开/关、每 IP 注册上限、上传字节帽）放在 `common.SiteSettings` 单例，Django admin 可改、`get_policy()` 快照给调用方、公开 `GET /site-policy/` 给 SPA。密钥与基础设施（`SECRET_KEY`、SMTP、Turnstile secret、`FRONTEND_URL`、MEDIA 路径）仍在 `config/settings.py` + `.env`，改完需重启。

调用方只 import `get_policy()`，不查模型。加旋钮 = 新字段 + 迁移 + 快照字段；不做 KV 袋。

## 被否方案

- **仅 env / settings**：改限流或关验证要redeploy，运维不够灵活。
- **django-constance / 通用 KV**：stringly typed、多一个依赖、调用方各解析各的。
- **SPA 编辑器**：写路径会扩大攻击面；已有 Django admin（`is_staff` + `change_sitesettings`）足够。
