from django.test import SimpleTestCase

from common.rich_text import sanitize_html


class RichTextSanitizeTest(SimpleTestCase):
    """共享净化器 sanitize_html 的白名单契约。

    被 news（新闻正文）与 about（关于页正文）共用——任何放宽都意味着全站富文本
    暴露面变化。覆盖：iframe 嵌入闸门、脚本/事件/协议清洗、白名单标签与属性放行。

    iframe 策略（2026-08-04 起）：允许任意 https iframe（不再做平台域白名单），补偿控制
    = 仅 https + 剥 srcdoc + 服务端统一盖 sandbox（不含 allow-top-navigation）。编辑者
    为受信角色；视觉钓鱼不归代码管。
    """

    def _clean(self, html):
        return sanitize_html(html)

    # ---- iframe 嵌入闸门（任意 https iframe；非域白名单）----
    def test_keeps_arbitrary_https_iframe(self):
        out = self._clean('<iframe src="https://embed.example.com/widget"></iframe>')
        self.assertIn("embed.example.com", out)
        self.assertIn("<iframe", out)

    def test_strips_http_iframe_src(self):
        # http src 被剥 → 空壳 iframe 被清（https 详情页本来也会被浏览器 mixed-content 拦）
        out = self._clean('<iframe src="http://embed.example.com/widget"></iframe>')
        self.assertNotIn("embed.example.com", out)
        self.assertNotIn("<iframe", out)

    def test_strips_iframe_srcdoc(self):
        # srcdoc 可内嵌任意 HTML/JS，必须剥离——即使同时带 https src 作掩护
        out = self._clean(
            '<iframe src="https://embed.example.com/x" srcdoc="<script>alert(1)</script>"></iframe>'
        )
        self.assertIn("embed.example.com", out)  # 合法 https src 保留
        self.assertNotIn("srcdoc", out)
        self.assertNotIn("<script", out)

    def test_strips_iframe_event_handler(self):
        out = self._clean('<iframe src="https://embed.example.com/x" onload="alert(1)"></iframe>')
        self.assertIn("embed.example.com", out)
        self.assertNotIn("onload", out)

    def test_iframe_forced_sandbox(self):
        # 服务端统一盖 sandbox 戳（用户未给）
        out = self._clean('<iframe src="https://embed.example.com/x"></iframe>')
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-popups allow-presentation"', out)

    def test_iframe_user_sandbox_overridden_no_top_navigation(self):
        # 用户粘的 sandbox（含 allow-top-navigation）必须被覆盖；出来只有一枚统一戳、且无 top-nav
        out = self._clean(
            '<iframe src="https://embed.example.com/x" sandbox="allow-scripts allow-top-navigation"></iframe>'
        )
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-popups allow-presentation"', out)
        self.assertNotIn("allow-top-navigation", out)
        self.assertEqual(out.count("sandbox="), 1)

    def test_iframe_user_allow_overridden(self):
        # 用户给的 allow（含 camera/geolocation 等 Permissions-Policy）必须被覆盖为只含播放所需
        out = self._clean(
            '<iframe src="https://embed.example.com/x" allow="camera; microphone; geolocation; payment"></iframe>'
        )
        self.assertIn('allow="autoplay; fullscreen; picture-in-picture"', out)
        self.assertNotIn("camera", out)
        self.assertNotIn("geolocation", out)
        self.assertNotIn("payment", out)
        self.assertEqual(out.count("allow="), 1)

    def test_keeps_video_tag(self):
        out = self._clean('<video src="https://cdn.example.com/x.mp4" controls></video>')
        self.assertIn("<video", out)
        self.assertIn("controls", out)
        self.assertIn("cdn.example.com/x.mp4", out)

    # ---- 脚本 / 事件 / 协议清洗 ----
    def test_strips_script_tag(self):
        out = self._clean('<p>ok</p><script>alert(1)</script>')
        self.assertNotIn("<script", out)
        self.assertIn("ok", out)  # strip=True：标签剥离，正文保留

    def test_strips_event_handler_attr(self):
        out = self._clean('<img src="https://e/x.png" onerror="alert(1)">')
        self.assertNotIn("onerror", out)
        self.assertIn("e/x.png", out)

    def test_strips_javascript_protocol(self):
        out = self._clean('<a href="javascript:alert(1)">x</a>')
        self.assertNotIn("javascript:", out)

    # ---- 白名单放行 ----
    def test_keeps_allowed_tags(self):
        out = self._clean('<h2>标题</h2><p>段落 <strong>加粗</strong></p>')
        self.assertIn("<h2>", out)
        self.assertIn("<strong>", out)
        self.assertIn("<p>", out)

    def test_keeps_class_attr(self):
        out = self._clean('<span class="marker">x</span>')
        self.assertIn("class=", out)
        self.assertIn("marker", out)

    # ---- 边界 ----
    def test_empty_passthrough(self):
        self.assertEqual(sanitize_html(""), "")
