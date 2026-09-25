"""问卷导出：统计聚合 + CSV / PDF 序列化（多问卷可聚合为单文件）。

供 Django admin 动作调用（``activities/admin.py``）。统计按题型聚合：
选择题给各选项计数（含未出现选项补零）、评分给均分与分布、文件题列出链接、
其余文本题列出全部回答。

PDF 以「问卷样式」渲染——题目卡片、选项勾选标记（单选 ●/○、多选 ■/□）、
评分星星、统计条形图——对齐前端 SurveyJS display 模式的观感；
JSON 导出已移除（仅保留 CSV / PDF）。

字体：随仓库分发 Noto Sans SC（activities/fonts/，SIL OFL），字形覆盖全
（· —— …… ★☆ 及生僻字等），不依赖运行环境安装的任何系统字体。
"""

import csv
import io
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from django.utils import timezone

# ── 题型归类（SurveyJS） ──
CHOICE_TYPES = {"radiogroup", "dropdown", "checkbox", "imagepicker", "tagbox", "buttongroup"}
MULTI_CHOICE_TYPES = {"checkbox", "tagbox"}
SCORE_TYPES = {"rating", "slider"}
FILE_TYPES = {"file", "signaturepad"}
SKIP_TYPES = {"html", "image", "expression", "custom"}

# 题型 → 中文标签（统计导出展示）
TYPE_LABELS = {
    "radiogroup": "单选",
    "dropdown": "下拉选择",
    "checkbox": "多选",
    "tagbox": "多选",
    "imagepicker": "图片选择",
    "buttongroup": "按钮组",
    "rating": "评分",
    "slider": "滑块评分",
    "text": "单行文本",
    "comment": "多行文本",
    "file": "文件上传",
    "signaturepad": "签名",
    "boolean": "是/否",
    "multipletext": "多填空",
}

# ── 视觉 token（前端 cobalt 主题的 sRGB 近似） ──
C_BRAND = "#0c63b4"       # brand-700 品牌动作色
C_BRAND_DARK = "#052b56"  # brand-900
C_BRAND_200 = "#b3d9fb"   # brand-200
C_BRAND_50 = "#ecf5fe"    # brand-50（选中底）
C_INK = "#1c2735"         # ink-900
C_MUTED = "#69737d"       # ink-500
C_FAINT = "#8e9aa6"       # ink-400
C_SOFT = "#f4f7fb"        # bg-soft
C_BAR_BG = "#e6edf6"

# 图表色板（品牌蓝阶；相邻色明度交替，便于区分）
PALETTE = [
    "#0c63b4", "#3da5f3", "#0a4f8f", "#79c2fa",
    "#1f87e0", "#5fb0e8", "#083b6e", "#a8d4f7",
]

PIE_MAX_SLICES = 8  # 选项超过该数时饼图/柱状图退回条形列表（标签会挤）

FONT = "NotoSansSC"
FONT_PATH = Path(__file__).resolve().parent / "fonts" / "NotoSansSC.ttf"
CONTENT_W = 483        # A4 宽 595pt − 左右边距 56pt × 2
EXPORT_TZ = ZoneInfo("Asia/Shanghai")  # 导出文件固定北京时间（settings 存储仍为 UTC）


def _type_label(t):
    return TYPE_LABELS.get(t, t)


def _local(dt):
    """转北京时间（导出文件面向国内阅读者）。"""
    return timezone.localtime(dt, EXPORT_TZ)


def extract_questions(schema):
    """从 SurveyJS schema 提取可作答题目（含嵌套 panel）。

    返回 [{name, title, type, choices, rate_max}]。
    """
    out = []

    def walk(elements):
        for el in elements or []:
            if not isinstance(el, dict):
                continue
            t = el.get("type") or ""
            if t in ("panel", "paneldynamic"):
                walk(el.get("elements"))
                continue
            if t in SKIP_TYPES:
                continue
            name = el.get("name")
            if not name:
                continue
            choices = []
            for c in el.get("choices") or []:
                if isinstance(c, dict):
                    choices.append(str(c.get("value", c.get("text", ""))))
                else:
                    choices.append(str(c))
            try:
                rate_max = int(el.get("rateMax") or 5)
            except (TypeError, ValueError):
                rate_max = 5
            out.append({
                "name": str(name),
                "title": el.get("title") or str(name),
                "type": t or "unknown",
                "choices": choices,
                "rate_max": rate_max,
            })

    for page in schema.get("pages") or []:
        if isinstance(page, dict):
            walk(page.get("elements"))
    walk(schema.get("elements"))
    return out


def _fmt_value(v):
    """答案值 → 文本（列表分号连接；dict 转 JSON）。"""
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join(_fmt_value(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _fmt_file(v):
    """文件题答案 → 文本（每行「文件名（链接）」）。"""
    items = v if isinstance(v, list) else [v]
    parts = []
    for it in items:
        if isinstance(it, dict):
            name = str(it.get("name") or "")
            url = str(it.get("content") or it.get("url") or "")
            parts.append(f"{name}（{url}）" if name else url)
        else:
            parts.append(str(it))
    return "\n".join(p for p in parts if p)


def compute_stats(schema, answers_list):
    """按题聚合统计。answers_list: list[dict]。"""
    stats = []
    for q in extract_questions(schema):
        name = q["name"]
        values = [
            a.get(name)
            for a in answers_list
            if isinstance(a, dict) and a.get(name) is not None
        ]
        entry = {"name": name, "title": q["title"], "type": q["type"], "answered": len(values)}
        if q["type"] in CHOICE_TYPES:
            counts = {}
            for v in values:
                vs = v if isinstance(v, list) else [v]
                for item in vs:
                    key = _fmt_value(item)
                    counts[key] = counts.get(key, 0) + 1
            for c in q["choices"]:
                counts.setdefault(c, 0)
            entry["counts"] = counts
        elif q["type"] in SCORE_TYPES:
            nums = []
            for v in values:
                try:
                    nums.append(float(str(v)))
                except (TypeError, ValueError):
                    pass
            entry["average"] = round(sum(nums) / len(nums), 2) if nums else None
            entry["rate_max"] = q.get("rate_max") or 5
            counts = {}
            for v in values:
                key = _fmt_value(v)
                counts[key] = counts.get(key, 0) + 1
            entry["counts"] = counts
        elif q["type"] in FILE_TYPES:
            files = []
            for v in values:
                vs = v if isinstance(v, list) else [v]
                for item in vs:
                    if isinstance(item, dict):
                        files.append(str(item.get("content") or item.get("name") or ""))
                    else:
                        files.append(str(item))
            entry["files"] = [f for f in files if f]
        else:
            entry["answers"] = [_fmt_value(v) for v in values]
        stats.append(entry)
    return stats


# ── CSV ──

def _sorted_counts(s):
    """(项, 计数) 列表；评分题按分值升序，其余保持题目定义序。"""
    items = list(s["counts"].items())
    if s["type"] in SCORE_TYPES:
        def key(kv):
            try:
                return (0, float(kv[0]))
            except (TypeError, ValueError):
                return (1, 0.0)
        items.sort(key=key)
    return items


def _stats_rows(stats):
    """统计 → 长格式行 [题目, 类型, 项目, 计数/内容]。"""
    rows = []
    for s in stats:
        t = _type_label(s["type"])
        if "counts" in s:
            if s.get("average") is not None:
                rows.append([s["title"], t, "平均分", s["average"]])
            for k, n in _sorted_counts(s):
                rows.append([s["title"], t, k, n])
        elif "files" in s:
            for f in s["files"]:
                rows.append([s["title"], t, f, ""])
        else:
            for a in s.get("answers", []):
                rows.append([s["title"], t, a, ""])
    return rows


def _stats_csv(sections):
    """统计 CSV。sections: [{title, stats}]；多份时加「问卷」列实现聚合。"""
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM：Excel 打开中文不乱码
    w = csv.writer(buf)
    multi = len(sections) > 1
    w.writerow(["问卷", "题目", "类型", "项目", "计数"] if multi else ["题目", "类型", "项目", "计数"])
    for sec in sections:
        for row in _stats_rows(sec["stats"]):
            w.writerow(([sec["title"]] + row) if multi else row)
    return buf.getvalue()


def _responses_csv(sections):
    """结果 CSV。sections: [{title, questions, data}]；多份时按问卷分块（块标题行分隔）。"""
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf)
    multi = len(sections) > 1
    for i, sec in enumerate(sections):
        if multi:
            if i:
                w.writerow([])
            w.writerow([f"问卷：{sec['title']}"])
        w.writerow(["用户", "提交时间"] + [q["title"] for q in sec["questions"]])
        for label, submitted, answers in sec["data"]:
            answers = answers or {}
            w.writerow(
                [label, _local(submitted).strftime("%Y-%m-%d %H:%M:%S")]
                + [_fmt_value(answers.get(q["name"])) for q in sec["questions"]]
            )
    return buf.getvalue()


# ── PDF（reportlab，内置中文 CID 字体；「问卷样式」渲染） ──

def _hex(s):
    from reportlab.lib.colors import HexColor
    return HexColor(s)


def _register_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT, str(FONT_PATH)))


_BAR_CLS = None


def _bar(frac, width=128, height=9, color=C_BRAND):
    """圆角比例条（统计图用）。"""
    global _BAR_CLS
    if _BAR_CLS is None:
        from reportlab.platypus.flowables import Flowable

        class _Bar(Flowable):
            def __init__(self, frac, width, height, color):
                super().__init__()
                self.frac = max(0.0, min(1.0, frac))
                self.width = width
                self.height = height
                self.color = color

            def wrap(self, aW, aH):
                return self.width, self.height

            def draw(self):
                c = self.canv
                r = self.height / 2
                c.setFillColor(_hex(C_BAR_BG))
                c.roundRect(0, 1, self.width, self.height, r, stroke=0, fill=1)
                if self.frac > 0:
                    c.setFillColor(_hex(self.color))
                    c.roundRect(0, 1, max(self.height, self.width * self.frac), self.height, r, stroke=0, fill=1)

        _BAR_CLS = _Bar
    return _BAR_CLS(frac, width, height, color)


def _para_styles():
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle

    def s(name, **kw):
        kw.setdefault("fontName", FONT)
        return ParagraphStyle(name, **kw)

    return {
        "h1": s("h1", fontSize=17, leading=24, textColor=C_BRAND_DARK),
        "sub": s("sub", fontSize=9.5, leading=14, textColor=C_MUTED),
        "q": s("q", fontSize=10.5, leading=15, textColor=C_INK),
        "opt": s("opt", fontSize=10, leading=14.5, textColor=C_INK),
        "ans": s("ans", fontSize=10, leading=15, textColor=C_INK),
        "muted": s("muted", fontSize=10, leading=15, textColor=C_FAINT),
        "meta": s("meta", fontSize=8.5, leading=12, textColor=C_MUTED),
        "head": s("head", fontSize=10.5, leading=15, textColor=C_BRAND_DARK),
        "num": s("num", fontSize=9.5, leading=14, textColor=C_INK, alignment=TA_RIGHT),
        "pct": s("pct", fontSize=9.5, leading=14, textColor=C_MUTED, alignment=TA_RIGHT),
        "legend": s("legend", fontSize=9, leading=15.5, textColor=C_INK),
    }


def _pdf_doc():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title="问卷导出",
        leftMargin=56,
        rightMargin=56,
        topMargin=54,
        bottomMargin=54,
    )
    return buf, doc


def _footer(canv, doc):
    canv.saveState()
    canv.setFont(FONT, 8.5)
    canv.setFillColor(_hex(C_MUTED))
    canv.drawCentredString(297.6, 32, f"问卷导出 · 第 {doc.page} 页")
    canv.restoreState()


def _section_head(title, sub, story, styles):
    from reportlab.platypus import HRFlowable, Paragraph, Spacer

    story.append(Paragraph(_esc(title), styles["h1"]))
    story.append(Paragraph(sub, styles["sub"]))
    story.append(Spacer(1, 5))
    story.append(HRFlowable(width="100%", thickness=1.5, color=_hex(C_BRAND)))
    story.append(Spacer(1, 12))


def _esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _choice_block(q, chosen, story, styles):
    """选项列表：勾选标记 + 选中行高亮（SurveyJS 观感）。"""
    from reportlab.platypus import Paragraph, Table, TableStyle

    multi = q["type"] in MULTI_CHOICE_TYPES
    mark_on, mark_off = ("■", "□") if multi else ("●", "○")
    choices = list(q["choices"] or [])
    extra = [v for v in chosen if v and v not in choices]  # 溢出值（如「其他」填写）
    rows = []
    sel_rows = []
    for i, c in enumerate(choices + extra):
        sel = c in chosen
        if sel:
            sel_rows.append(i)
        mcolor = C_BRAND if sel else C_FAINT
        tcolor = C_BRAND_DARK if sel else C_INK
        rows.append([
            Paragraph(f'<font color="{mcolor}">{mark_on if sel else mark_off}</font>', styles["opt"]),
            Paragraph(f'<font color="{tcolor}">{_esc(c)}</font>', styles["opt"]),
        ])

    t = Table(rows, colWidths=[20, CONTENT_W - 20])
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for i in sel_rows:
        cmds.append(("BACKGROUND", (0, i), (1, i), _hex(C_BRAND_50)))
    t.setStyle(TableStyle(cmds))
    story.append(t)


def _text_block(text, story, styles):
    """文本答案卡片：浅底 + 左侧品牌色竖线。"""
    from reportlab.platypus import Paragraph, Table, TableStyle

    t = Table([[Paragraph(text, styles["ans"])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _hex(C_SOFT)),
        ("LINEBEFORE", (0, 0), (0, 0), 3, _hex(C_BRAND_200)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(t)


def _score_block(q, v, story, styles):
    """评分：星星 + 数值。"""
    from reportlab.platypus import Paragraph

    try:
        num = float(str(v))
    except (TypeError, ValueError):
        story.append(Paragraph("（未作答）", styles["muted"]))
        return
    mx = int(q.get("rate_max") or 5)
    n = max(0, min(mx, int(round(num))))
    stars = "★" * n + "☆" * (mx - n)
    story.append(Paragraph(
        f'<font color="{C_BRAND}">{stars}</font>　{num:g} / {mx}',
        styles["ans"],
    ))


def _answer_of(q, v, story, styles):
    """单题答案渲染（按题型分发）。"""
    from reportlab.platypus import Paragraph

    empty = v is None or v == "" or v == []
    if empty:
        story.append(Paragraph("（未作答）", styles["muted"]))
        return
    if q["type"] in CHOICE_TYPES and q["choices"]:
        chosen = {_fmt_value(x) for x in (v if isinstance(v, list) else [v])}
        _choice_block(q, chosen, story, styles)
    elif q["type"] in SCORE_TYPES:
        _score_block(q, v, story, styles)
    elif q["type"] in FILE_TYPES:
        _text_block(_esc(_fmt_file(v)), story, styles)
    else:
        _text_block(_esc(_fmt_value(v)), story, styles)


def _answer_block(label, submitted, questions, answers, story, styles):
    """一份作答：信息条 + 逐题渲染。"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    answers = answers or {}
    head = Table(
        [[Paragraph(f"{_esc(label)}　·　{_local(submitted).strftime('%Y-%m-%d %H:%M')}", styles["head"])]],
        colWidths=[CONTENT_W],
    )
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _hex(C_BRAND_50)),
        ("LINEBEFORE", (0, 0), (0, 0), 3.5, _hex(C_BRAND)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(head)
    story.append(Spacer(1, 9))

    for q in questions:
        story.append(Paragraph(_esc(q["title"]), styles["q"]))
        story.append(Spacer(1, 3))
        _answer_of(q, answers.get(q["name"]), story, styles)
        story.append(Spacer(1, 10))
    story.append(Spacer(1, 6))


def _counts_table(items, total, styles):
    """计数条形列表（选项 / 比例条 / 计数 / 百分比）。"""
    from reportlab.platypus import Paragraph, Table, TableStyle

    rows = []
    for k, n in items:
        frac = n / total
        rows.append([
            Paragraph(_esc(k), styles["opt"]),
            _bar(frac),
            Paragraph(str(n), styles["num"]),
            Paragraph(f"{frac:.0%}", styles["pct"]),
        ])
    t = Table(rows, colWidths=[240, 133, 55, 55])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _pie_chart(items, total, styles):
    """饼图 + 图例列表（色块 / 文本 / 计数 / 百分比）并排。"""
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing
    from reportlab.platypus import Paragraph, Table, TableStyle

    d = Drawing(150, 150)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 22, 22, 106, 106
    pie.data = [c for _, c in items]
    pie.slices.strokeWidth = 1.2
    pie.slices.strokeColor = _hex("#ffffff")
    for i in range(len(items)):
        pie.slices[i].fillColor = _hex(PALETTE[i % len(PALETTE)])
    d.add(pie)

    legend = []
    for i, (label, c) in enumerate(items):
        color = PALETTE[i % len(PALETTE)]
        pct = (c / total) if total else 0
        legend.append(Paragraph(
            f'<font color="{color}">■</font> {_esc(label)}　'
            f'<font color="{C_MUTED}">{c}（{pct:.0%}）</font>',
            styles["legend"],
        ))

    t = Table([[d, legend]], colWidths=[160, CONTENT_W - 160])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _vbar_chart(items):
    """垂直柱状图（柱顶计数）；适用于评分分布与选项较少的分布。"""
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing

    n = len(items)
    max_v = max((c for _, c in items), default=1) or 1
    step = 1 if max_v <= 10 else (5 if max_v <= 40 else 10)
    top = ((max_v + step - 1) // step) * step

    width, height = CONTENT_W - 4, 152
    d = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x, bc.y = 36, 30
    bc.width, bc.height = width - 50, height - 48
    bc.data = [[c for _, c in items]]
    bc.categoryAxis.categoryNames = [str(l) for l, _ in items]
    bc.categoryAxis.labels.fontName = FONT
    bc.categoryAxis.labels.fontSize = 7.5
    bc.categoryAxis.labels.dy = -7
    bc.valueAxis.labels.fontName = FONT
    bc.valueAxis.labels.fontSize = 7.5
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = top
    bc.valueAxis.valueStep = step
    bc.barWidth = 18 if n <= 6 else 12
    bc.bars[0].fillColor = _hex(C_BRAND)
    bc.barLabelFormat = "%d"
    bc.barLabels.fontName = FONT
    bc.barLabels.fontSize = 8
    bc.barLabels.dy = 2
    d.add(bc)
    return d


def _stats_block(s, story, styles):
    """单题统计渲染。"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    story.append(Paragraph(_esc(s["title"]), styles["q"]))
    story.append(Paragraph(
        f'<font color="{C_FAINT}">{_esc(_type_label(s["type"]))} · 作答 {s["answered"]} 份</font>',
        styles["meta"],
    ))
    story.append(Spacer(1, 4))

    if "counts" in s:
        counts = s["counts"]
        total = sum(counts.values()) or 1
        if s.get("average") is not None:
            mx = int(s.get("rate_max") or 5)
            avg = s["average"]
            n = max(0, min(mx, int(round(avg))))
            stars = "★" * n + "☆" * (mx - n)
            story.append(Paragraph(
                f'平均分：<font color="{C_BRAND}">{stars}</font>　{avg:g} / {mx}',
                styles["ans"],
            ))
            story.append(Spacer(1, 4))
        items = _sorted_counts(s)
        if not items:
            story.append(Paragraph("（暂无作答）", styles["muted"]))
        elif s["type"] in SCORE_TYPES:
            story.append(_vbar_chart(items))          # 评分分布：柱状图
        elif s["type"] in MULTI_CHOICE_TYPES:
            if len(items) <= PIE_MAX_SLICES:
                story.append(_vbar_chart(items))      # 多选：柱状图
            else:
                story.append(_counts_table(items, total, styles))
        elif s["type"] in CHOICE_TYPES:
            if len(items) <= PIE_MAX_SLICES:
                story.append(_pie_chart(items, total, styles))  # 单选：饼图
            else:
                story.append(_counts_table(items, total, styles))
        else:
            story.append(_counts_table(items, total, styles))
    elif "files" in s:
        for f in s["files"]:
            story.append(Paragraph(_esc(f), styles["ans"]))
    else:
        for i, a in enumerate(s.get("answers", []), 1):
            story.append(Paragraph(f"{i}. {_esc(a)}", styles["ans"]))
    story.append(Spacer(1, 14))


def _responses_pdf(sections):
    """作答 PDF。sections: [{title, count, questions, data}]；多份分页聚合。"""
    from reportlab.platypus import PageBreak

    _register_font()
    buf, doc = _pdf_doc()
    styles = _para_styles()
    now = _local(timezone.now()).strftime("%Y-%m-%d %H:%M")
    story = []
    for i, sec in enumerate(sections):
        if i:
            story.append(PageBreak())
        _section_head(sec["title"], f"导出时间：{now}　共 {len(sec['data'])} 份作答", story, styles)
        for label, submitted, answers in sec["data"]:
            _answer_block(label, submitted, sec["questions"], answers, story, styles)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _stats_pdf(sections):
    """统计 PDF。sections: [{title, count, stats}]；多份分页聚合。"""
    from reportlab.platypus import PageBreak

    _register_font()
    buf, doc = _pdf_doc()
    styles = _para_styles()
    now = _local(timezone.now()).strftime("%Y-%m-%d %H:%M")
    story = []
    for i, sec in enumerate(sections):
        if i:
            story.append(PageBreak())
        _section_head(sec["title"], f"导出时间：{now}　作答总数：{sec['count']}", story, styles)
        for s in sec["stats"]:
            _stats_block(s, story, styles)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ── 顶层：供 admin 调用 ──

def _label(row):
    if row.user_id:
        return row.user.username
    if row.device_id:
        return f"访客·{row.device_id[:8]}"
    return "访客"


def _batch_name(kind, qs, ext):
    if len(qs) == 1:
        return f"survey-{kind}-{qs[0].pk}.{ext}"
    stamp = _local(timezone.now()).strftime("%Y%m%d")
    return f"survey-{kind}-batch-{len(qs)}-{stamp}.{ext}"


def export_stats(questionnaires, fmt):
    """导出统计（1..N 份问卷聚合为单个文件）。

    questionnaires: 可迭代的 Questionnaire；返回 (data: bytes, content_type, filename)。
    """
    qs = list(questionnaires)
    sections = []
    for q in qs:
        schema = q.schema or {}
        answers_list = [r.answers or {} for r in q.responses.all()]
        sections.append({
            "title": schema.get("title") or f"#{q.pk}",
            "count": len(answers_list),
            "stats": compute_stats(schema, answers_list),
        })
    if fmt == "csv":
        return _stats_csv(sections).encode("utf-8"), "text/csv; charset=utf-8", _batch_name("stats", qs, "csv")
    if fmt == "pdf":
        return _stats_pdf(sections), "application/pdf", _batch_name("stats", qs, "pdf")
    raise ValueError(f"unsupported format: {fmt}")


def export_responses(questionnaires, fmt):
    """导出全部作答（1..N 份问卷聚合为单个文件）。

    questionnaires: 可迭代的 Questionnaire；返回 (data: bytes, content_type, filename)。
    """
    qs = list(questionnaires)
    sections = []
    for q in qs:
        schema = q.schema or {}
        rows = list(q.responses.select_related("user").all())
        sections.append({
            "title": schema.get("title") or f"#{q.pk}",
            "questions": extract_questions(schema),
            "data": [(_label(r), r.submitted_at, r.answers or {}) for r in rows],
        })
    if fmt == "csv":
        return _responses_csv(sections).encode("utf-8"), "text/csv; charset=utf-8", _batch_name("responses", qs, "csv")
    if fmt == "pdf":
        return _responses_pdf(sections), "application/pdf", _batch_name("responses", qs, "pdf")
    raise ValueError(f"unsupported format: {fmt}")
