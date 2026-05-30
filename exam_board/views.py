from django.shortcuts import render

# Create your views here.
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ExamData  # 引入ExamData 模型


@csrf_exempt
def upload_data(request):
    """功能一：数据上传（支持同时存入标题和考试列表）"""
    if request.method == 'POST':
        try:
            # 解析前端传过来的 JSON 数据
            data = json.loads(request.body)
            title = data.get('exam_title', '')
            ex_list = data.get('exam_list', '')

            # 往数据库创建一条新记录
            ExamData.objects.create(
                exam_title=title,
                exam_list=ex_list
            )
            return JsonResponse({"status": "success", "message": "考试看板数据保存成功！"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "请使用 POST 方法上传数据"})


def read_data(request):
    """功能二：数据读取（获取最新的一条考试数据）"""
    # 获取数据库里最新创建的一条数据
    last_exam = ExamData.objects.last()

    if last_exam:
        return JsonResponse({
            "status": "success",
            "data": {
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
