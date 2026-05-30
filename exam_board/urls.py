from django.urls import path
from . import views

urlpatterns = [
    # 访问 /exam_board/upload/ 触发上传
    path('upload/', views.upload_data, name='upload_data'),
    # 访问 /exam_board/read/ 触发读取
    path('read/', views.read_data, name='read_data'),
]
