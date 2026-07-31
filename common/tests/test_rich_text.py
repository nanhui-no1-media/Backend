from django.test import SimpleTestCase

from common.rich_text import sanitize_html


class RichTextSanitizeTest(SimpleTestCase):
    """共享净化器 sanitize_html 的白名单契约。

    被 news（新闻正文）与 about（关于页正文）共用——任何放宽都意味着全站富文本
    暴露面变化。覆盖：视频外链嵌入闸门、脚本/事件/协议清洗、白名单标签与属性放行。
    """

    def _clean(self, html):
        return sanitize_html(html)

    # ---- 视频外链嵌入闸门 ----
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
