"""共享富文本 HTML 净化器。

服务端清洗可挡住成员绕过编辑器、直接经 API 注入的 <script> / 事件处理器 / javascript: 等。
被 news（新闻正文）与 about（关于页正文）共用——白名单与前端 RichTextEditor
（TipTap：StarterKit + TaskList + Table + Image + Video）输出对齐。
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


# bleach 对白名单内的 <iframe> 仅剥离非法属性（如未通过域名白名单的 src），留下空壳
# <iframe></iframe>；此处把「无 src 的 iframe」整体移除（即 src 未过白名单或缺失者）。
_IFRAME_WITHOUT_SRC_RE = re.compile(
    r"<iframe\b(?![^>]*\bsrc=)[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL,
)

_ALLOWED_ATTRS = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "iframe": _iframe_src_filter,
    "video": ["src", "controls", "preload", "width", "height", "poster"],
    "th": ["colspan", "rowspan", "colwidth"],
    "td": ["colspan", "rowspan", "colwidth"],
    "ul": ["class", "data-type"],
    "ol": ["class", "data-type"],
    "li": ["class", "data-type", "data-checked"],
}
_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]


def sanitize_html(html: str) -> str:
    """清洗正文 HTML：仅保留白名单标签/属性/协议，其余剥离（strip=True，内容保留）。"""
    if not html:
        return html
    cleaned = bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    # 移除 src 被清洗掉的空壳 iframe（见 _IFRAME_WITHOUT_SRC_RE）。
    return _IFRAME_WITHOUT_SRC_RE.sub("", cleaned)
