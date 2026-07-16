from django.db import migrations

INFO_GROUP_NAME = "信息组"


def create_info_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=INFO_GROUP_NAME)


def remove_info_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=INFO_GROUP_NAME).delete()


class Migration(migrations.Migration):
    """幂等地创建「信息组」组（负责新闻发布与账户分发）。

    依赖 auth.Group —— news.0001_initial 已通过 AUTH_USER_MODEL 间接依赖 auth，
    这里再显式声明以保证 apps.get_model("auth","Group") 可用。
    """

    dependencies = [
        ("news", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_info_group, reverse_code=remove_info_group),
    ]
