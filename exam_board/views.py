from django.shortcuts import render

# Create your views here.
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ExamData  


@csrf_exempt
def upload_data(request):
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
