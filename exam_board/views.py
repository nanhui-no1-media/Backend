from django.shortcuts import render

# Create your views here.
import json
from django.http import JsonResponse
from .models import ExamData


def upload_data(request):
    """上传考卷数据（#33 安全修复）：原 @csrf_exempt + 无鉴权 → 匿名可任意上传。

    最低修复：要求登录（未登录 401）并恢复 CSRF 保护（移除 @csrf_exempt）。
    进一步收紧（仅信息组可用 / 文件类型大小校验）见 #33 triage 后续。
    """
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "请先登录。"}, status=401)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date = data.get("exam_date", "")
            title = data.get('exam_title', '')
            ex_list = data.get('exam_list', '')

            ExamData.objects.create(
                exam_date=date,
                exam_title=title,
                exam_list=ex_list
            )
            return JsonResponse({"status": "success", "message": "考试数据保存成功！"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "请使用 POST 方法上传数据"})


def read_data(request):
    last_exam = ExamData.objects.last()

    if last_exam:
        return JsonResponse({
            "status": "success",
            "data": {
                "exam_date": last_exam.exam_date,
                "exam_title": last_exam.exam_title,
                "exam_list": last_exam.exam_list
            }
        })
    else:
        return JsonResponse({
            "status": "success",
            "data": None,
            "message": "数据库中暂无考试数据"
        })
