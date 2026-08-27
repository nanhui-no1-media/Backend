"""存量新闻 / 活动 / 任务各补一条开放评论区。不把旧任务/申报消息转成评论。"""
from django.db import migrations


def backfill(apps, schema_editor):
    CommentThread = apps.get_model("messaging", "CommentThread")
    News = apps.get_model("news", "News")
    Activity = apps.get_model("activities", "Activity")
    Task = apps.get_model("tasks", "Task")

    for news in News.objects.all().iterator():
        CommentThread.objects.get_or_create(
            news_id=news.pk, defaults={"status": "open"},
        )
    for activity in Activity.objects.all().iterator():
        CommentThread.objects.get_or_create(
            activity_id=activity.pk, defaults={"status": "open"},
        )
    for task in Task.objects.all().iterator():
        CommentThread.objects.get_or_create(
            task_id=task.pk, defaults={"status": "open"},
        )


def unfill(apps, schema_editor):
    CommentThread = apps.get_model("messaging", "CommentThread")
    CommentThread.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0002_banner_remove_conversation_conversation_type_and_more"),
        ("news", "0003_remove_news_category"),
        ("activities", "0013_questionnaire"),
        ("tasks", "0002_delete_attachment"),
    ]

    operations = [
        migrations.RunPython(backfill, unfill),
    ]
