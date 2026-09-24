"""问卷导出：统计聚合 + 结果序列化（CSV / JSON / PDF）。

供 Django admin 动作调用（``activities/admin.py``）。统计按题型聚合：
选择题给各选项计数（含未出现选项补零）、评分给均分与分布、文件题列出链接、
其余文本题列出全部回答。PDF 用 reportlab 内置中文 CID 字体（STSong-Light）。
"""

import csv
import io
import json

from django.utils import timezone

# 题型归类（SurveyJS）
CHOICE_TYPES = {"radiogroup", "dropdown", "checkbox", "imagepicker", "tagbox", "buttongroup"}
SCORE_TYPES = {"rating", "slider"}
FILE_TYPES = {"file", "signaturepad"}
SKIP_TYPES = {"html", "image", "expression", "custom"}


def extract_questions(schema):
    """从 SurveyJS schema 提取可作答题目（含嵌套 panel），返回 [{name,title,type,choices}]。"""
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
            out.append({
                "name": str(name),
                "title": el.get("title") or str(name),
                "type": t or "unknown",
                "choices": choices,
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


# ── 统计行 / CSV ──

def _stats_rows(stats):
    """统计 → 长格式行 [题目, 类型, 项目, 计数/内容]。"""
    rows = []
    for s in stats:
        if "counts" in s:
            if s.get("average") is not None:
                rows.append([s["title"], s["type"], "平均分", s["average"]])
            for k, n in s["counts"].items():
                rows.append([s["title"], s["type"], k, n])
        elif "files" in s:
            for f in s["files"]:
                rows.append([s["title"], s["type"], f, ""])
        else:
            for a in s.get("answers", []):
                rows.append([s["title"], s["type"], a, ""])
    return rows


def _stats_csv(stats):
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM：Excel 打开中文不乱码
    w = csv.writer(buf)
    w.writerow(["题目", "类型", "项目", "计数"])
    for row in _stats_rows(stats):
        w.writerow(row)
    return buf.getvalue()


def _responses_csv(questions, data):
    """结果 CSV：一行一作答。data: [(label, submitted_at, answers)]。"""
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(["用户", "提交时间"] + [q["title"] for q in questions])
    for label, submitted, answers in data:
        answers = answers or {}
        w.writerow(
            [label, submitted.strftime("%Y-%m-%d %H:%M:%S")]
            + [_fmt_value(answers.get(q["name"])) for q in questions]
        )
    return buf.getvalue()


# ── PDF（reportlab，内置中文 CID 字体）──

def _pdf_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    title = ParagraphStyle("title", fontName="STSong-Light", fontSize=16, leading=24, spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName="STSong-Light", fontSize=12.5, leading=19, spaceBefore=10, spaceAfter=3)
    body = ParagraphStyle("body", fontName="STSong-Light", fontSize=10, leading=16)
    return title, h2, body


def _esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _pdf_doc():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="问卷导出")
    return buf, doc


def _stats_pdf(questionnaire, stats):
    from reportlab.platypus import Paragraph, Spacer

    buf, doc = _pdf_doc()
    title_s, h2_s, body_s = _pdf_styles()
    schema_title = (questionnaire.schema or {}).get("title") or f"#{questionnaire.pk}"
    story: list = [Paragraph(f"问卷统计：{_esc(schema_title)}", title_s)]
    story.append(Paragraph(
        f"导出时间：{timezone.localtime().strftime('%Y-%m-%d %H:%M')}"
        f"　作答总数：{questionnaire.responses.count()}",
        body_s,
    ))
    for s in stats:
        story.append(Paragraph(
            f"◆ {_esc(s['title'])}（{_esc(s['type'])}，作答 {s['answered']} 份）", h2_s,
        ))
        if "counts" in s:
            if s.get("average") is not None:
                story.append(Paragraph(f"　平均分：{s['average']}", body_s))
            for k, n in s["counts"].items():
                story.append(Paragraph(f"　{_esc(k)}：{n}", body_s))
        elif "files" in s:
            for f in s["files"]:
                story.append(Paragraph(f"　{_esc(f)}", body_s))
        else:
            for a in s.get("answers", []):
                story.append(Paragraph(f"　{_esc(a)}", body_s))
        story.append(Spacer(1, 4))
    doc.build(story)
    return buf.getvalue()


def _responses_pdf(questionnaire, questions, data):
    from reportlab.platypus import Paragraph, Spacer

    buf, doc = _pdf_doc()
    title_s, h2_s, body_s = _pdf_styles()
    schema_title = (questionnaire.schema or {}).get("title") or f"#{questionnaire.pk}"
    story: list = [Paragraph(f"问卷结果：{_esc(schema_title)}", title_s)]
    story.append(Paragraph(
        f"导出时间：{timezone.localtime().strftime('%Y-%m-%d %H:%M')}　共 {len(data)} 份作答",
        body_s,
    ))
    for label, submitted, answers in data:
        answers = answers or {}
        story.append(Paragraph(
            f"◆ {_esc(label)}（{submitted.strftime('%Y-%m-%d %H:%M')}）", h2_s,
        ))
        for q in questions:
            v = _fmt_value(answers.get(q["name"]))
            if v:
                story.append(Paragraph(f"　{_esc(q['title'])}：{_esc(v)}", body_s))
        story.append(Spacer(1, 6))
    doc.build(story)
    return buf.getvalue()


# ── 顶层：供 admin 调用 ──

def _label(row):
    if row.user_id:
        return row.user.username
    if row.device_id:
        return f"访客·{row.device_id[:8]}"
    return "访客"


def export_stats(questionnaire, fmt):
    """导出统计。返回 (data: bytes, content_type, filename)。"""
    schema = questionnaire.schema or {}
    answers_list = [r.answers or {} for r in questionnaire.responses.all()]
    stats = compute_stats(schema, answers_list)
    slug = f"survey-stats-{questionnaire.pk}"
    if fmt == "csv":
        return _stats_csv(stats).encode("utf-8"), "text/csv; charset=utf-8", f"{slug}.csv"
    if fmt == "json":
        payload = {
            "questionnaire_id": questionnaire.pk,
            "title": schema.get("title") or "",
            "exported_at": timezone.now().isoformat(),
            "response_count": len(answers_list),
            "stats": stats,
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            f"{slug}.json",
        )
    if fmt == "pdf":
        return _stats_pdf(questionnaire, stats), "application/pdf", f"{slug}.pdf"
    raise ValueError(f"unsupported format: {fmt}")


def export_responses(questionnaire, fmt):
    """导出全部作答。返回 (data: bytes, content_type, filename)。"""
    schema = questionnaire.schema or {}
    questions = extract_questions(schema)
    rows = list(questionnaire.responses.select_related("user").all())
    data = [(_label(r), r.submitted_at, r.answers or {}) for r in rows]
    slug = f"survey-responses-{questionnaire.pk}"
    if fmt == "csv":
        return (
            _responses_csv(questions, data).encode("utf-8"),
            "text/csv; charset=utf-8",
            f"{slug}.csv",
        )
    if fmt == "json":
        payload = {
            "questionnaire_id": questionnaire.pk,
            "title": schema.get("title") or "",
            "exported_at": timezone.now().isoformat(),
            "questions": questions,
            "responses": [
                {
                    "user_label": label,
                    "submitted_at": submitted.isoformat(),
                    "answers": answers,
                }
                for label, submitted, answers in data
            ],
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            f"{slug}.json",
        )
    if fmt == "pdf":
        return (
            _responses_pdf(questionnaire, questions, data),
            "application/pdf",
            f"{slug}.pdf",
        )
    raise ValueError(f"unsupported format: {fmt}")
