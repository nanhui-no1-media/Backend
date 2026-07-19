from django.db import migrations


def seed(apps, schema_editor):
    from django.contrib.auth.management import create_permissions
    from django.contrib.contenttypes.management import create_contenttypes
    from django.apps import apps as real_apps

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # 自定义权限由 post_migrate 在「全部迁移跑完后」才创建；
    # 数据迁移执行期间尚未存在 → 先强制建出 contenttypes 与权限，保证下方能查到。
    for app_config in real_apps.get_app_configs():
        create_contenttypes(app_config, apps=apps, verbosity=0)
        create_permissions(app_config, apps=apps, verbosity=0)

    GROUP_PERMISSIONS = {
        "信息组": [
            ("news", "add_news"),
            ("news", "change_news"),
            ("news", "delete_news"),
        ],
        "社长": [
            ("tasks", "manage_tasks"),
            ("tasks", "assign_task"),
            ("tasks", "manage_tags"),
            ("proposals", "approve_proposal"),
            ("proposals", "view_feedback"),
            ("proposals", "change_proposal"),
        ],
    }
    for group_name, codenames in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for app_label, codename in codenames:
            perm = Permission.objects.get(
                content_type__app_label=app_label, codename=codename
            )
            group.permissions.add(perm)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_usersession"),
        ("news", "0002_create_info_group"),
        ("tasks", "0005_alter_tag_options_alter_task_options"),
        ("proposals", "0002_alter_proposal_options"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
