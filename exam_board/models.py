from django.db import models


# Create your models here.
class ExamData(models.Model):
    exam_title = models.CharField(max_length=50, blank=True)  # 考试标题
    exam_list = models.CharField(max_length=255, blank=True)  # 考试列表

    def __str__(self):
        return self.exam_title