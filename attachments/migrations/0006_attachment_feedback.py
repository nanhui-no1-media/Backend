"""Retarget Attachment.proposal → Attachment.feedback, then drop the proposal FK."""
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F


def copy_proposal_fk(apps, schema_editor):
    Attachment = apps.get_model("attachments", "Attachment")
    Attachment.objects.filter(proposal_id__isnull=False).update(feedback_id=F("proposal_id"))


class Migration(migrations.Migration):

    dependencies = [
        ("attachments", "0005_remove_attachment_attachment_exactly_one_parent_and_more"),
        ("reviews", "0007_copy_proposals_to_feedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="attachment",
            name="feedback",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attachments",
                to="reviews.feedback",
                verbose_name="意见反馈",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="attachment",
            name="attachment_exactly_one_parent",
        ),
        migrations.RunPython(copy_proposal_fk, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="attachment",
            name="proposal",
        ),
        migrations.AddConstraint(
            model_name="attachment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(exhibit__isnull=True, feedback__isnull=True, news__isnull=True, submission__isnull=True, task__isnull=False)
                    | models.Q(exhibit__isnull=True, feedback__isnull=False, news__isnull=True, submission__isnull=True, task__isnull=True)
                    | models.Q(exhibit__isnull=True, feedback__isnull=True, news__isnull=False, submission__isnull=True, task__isnull=True)
                    | models.Q(exhibit__isnull=True, feedback__isnull=True, news__isnull=True, submission__isnull=False, task__isnull=True)
                    | models.Q(exhibit__isnull=False, feedback__isnull=True, news__isnull=True, submission__isnull=True, task__isnull=True)
                ),
                name="attachment_exactly_one_parent",
                violation_error_message="附件必须且只能挂在一个父级（任务/意见反馈/新闻/作品/展品）上。",
            ),
        ),
    ]
