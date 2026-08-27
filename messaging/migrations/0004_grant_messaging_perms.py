"""授予「社长」组 mute_user + manage_comment_thread；「信息组」manage_announcement。

与 reviews/0003_grant_moderate_to_president 同模式：先确保 Permission 行已生成。
"""
from django.db import migrations


def grant(apps, schema_editor):
    from django.contrib.auth.management import create_permissions
    from django.contrib.contenttypes.management import create_contenttypes
    from django.apps import apps as real_apps

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for app_config in real_apps.get_app_configs():
        create_contenttypes(app_config, apps=apps, verbosity=0)
        create_permissions(app_config, apps=apps, verbosity=0)

    president, _ = Group.objects.get_or_create(name="社长")
    for codename in ("mute_user", "manage_comment_thread"):
        perm = Permission.objects.get(
            content_type__app_label="messaging", codename=codename,
        )
        president.permissions.add(perm)

    info, _ = Group.objects.get_or_create(name="信息组")
    perm = Permission.objects.get(
        content_type__app_label="messaging", codename="manage_announcement",
    )
    info.permissions.add(perm)


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0003_backfill_comment_threads"),
        ("accounts", "0002_seed_default_groups"),
    ]

    operations = [
        migrations.RunPython(grant, migrations.RunPython.noop),
    ]
