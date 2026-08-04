"""共享富文本 HTML 净化器。

服务端清洗可挡住成员绕过编辑器、直接经 API 注入的 <script> / 事件处理器 / javascript: 等。
被 news（新闻正文）与 about（关于页正文）共用——白名单与前端 RichTextEditor
（TipTap：StarterKit + TaskList + Table + Image + Video + Iframe）输出对齐。
"""
import bleach
import re
import urllib.parse

# 正文 HTML 白名单
_ALLOWED_TAGS = [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "s", "del", "u", "mark", "code", "sub", "sup",
    "pre", "blockquote",
    "ul", "ol", "li",
    "a", "img", "iframe", "video",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "figure", "figcaption", "span",
]

# iframe 策略（2026-08-04 起）：允许任意 https iframe（不再做平台域白名单）——编辑者
# （信息组 / about 编辑）为受信角色。补偿控制：
#   - 仅 https（http / 相对 / javascript: 的 src 一律剥，剥后空壳 iframe 由正则清除）；
#   - srcdoc 一律剥（防内嵌任意 HTML/JS，即便带 https src 作掩护）；
#   - 用户给的 sandbox 与 allow（Permissions-Policy）一律作废，由服务端统一盖戳（见
#     _IFRAME_SANDBOX / _IFRAME_ALLOW）——sandbox 故意不给 allow-top-navigation（防 top-nav
#     重定向钓鱼），allow 仅放行播放所需（不放 camera/mic/geolocation/payment）；
#   - 事件处理器（onload 等）/ <script> 仍被 bleach 挡。
# 残面：视觉钓鱼（假登录框）不归代码管，靠角色信任兜底。
#
# iframe 允许的属性（src 单独判 https；srcdoc / sandbox / allow / on* 均不在此 → 被剥，由服务端统一盖戳）。
_IFRAME_SAFE_ATTRS = frozenset({"frameborder", "width", "height", "loading", "title"})
# 服务端强制盖戳的 sandbox 值：跨源 embed 所需最小集；不含 allow-top-navigation（防 top-nav 钓鱼）。
_IFRAME_SANDBOX = "allow-scripts allow-same-origin allow-popups allow-presentation"
# 服务端强制盖戳的 allow（Permissions-Policy）值：仅播放所需，不放 camera/mic/geolocation/payment。
_IFRAME_ALLOW = "autoplay; fullscreen; picture-in-picture"


def _iframe_attr_filter(tag, name, value):
    """bleach 属性回调：iframe 的 src 仅放行 https（http / 相对 / javascript: 一律剥，剥后
    空壳 iframe 由 _IFRAME_WITHOUT_SRC_RE 清除）；其余属性须在安全白名单内（srcdoc / sandbox /
    allow / onload 等不在内 → 剥离；sandbox 与 allow 由 _stamp_iframe_attrs 统一盖戳）。"""
    if name == "src":
        try:
            return urllib.parse.urlparse(value).scheme == "https"
        except (ValueError, TypeError):
            return False
    return name in _IFRAME_SAFE_ATTRS


# 清除 src 被剥（http / 非法 / 缺失）的空壳 iframe：bleach 仅剥属性留 <iframe></iframe> 空壳。
_IFRAME_WITHOUT_SRC_RE = re.compile(
    r"<iframe\b(?![^>]*\bsrc=)[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL,
)
# 给（已被 bleach 剥掉用户 sandbox/allow 的）存活 iframe 统一注入 sandbox+allow 戳。仅匹配尚无 sandbox 者，幂等。
_IFRAME_STAMP_RE = re.compile(r"<iframe\b(?![^>]*\bsandbox=)", re.IGNORECASE)


def _stamp_iframe_attrs(html: str) -> str:
    """给每个存活 iframe 注入统一 sandbox + allow 戳（用户粘的 sandbox/allow 已被 _iframe_attr_filter 剥）。"""
    return _IFRAME_STAMP_RE.sub(
        f'<iframe sandbox="{_IFRAME_SANDBOX}" allow="{_IFRAME_ALLOW}"', html
    )


_ALLOWED_ATTRS = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "iframe": _iframe_attr_filter,
    "video": ["src", "controls", "preload", "width", "height", "poster"],
    "th": ["colspan", "rowspan", "colwidth"],
    "td": ["colspan", "rowspan", "colwidth"],
    "ul": ["class", "data-type"],
    "ol": ["class", "data-type"],
    "li": ["class", "data-type", "data-checked"],
}
_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]


def sanitize_html(html: str) -> str:
    """清洗正文 HTML：仅保留白名单标签/属性/协议，其余剥离（strip=True，内容保留）；
    iframe 仅放行 https src、剥 srcdoc/用户 sandbox/用户 allow，存活者统一盖 sandbox+allow 戳。"""
    if not html:
        return html
    cleaned = bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    cleaned = _IFRAME_WITHOUT_SRC_RE.sub("", cleaned)  # 清 http / 无 src 的空壳 iframe
    return _stamp_iframe_attrs(cleaned)
