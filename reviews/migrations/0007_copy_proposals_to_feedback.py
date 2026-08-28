"""Copy leftover Proposal rows into reviews.Feedback (same primary keys)."""
from django.db import migrations


_STATUS = {
    "pending_approval": "pending",
    "approved": "closed",
    "rejected": "closed",
    "withdrawn": "closed",
}
_CATEGORY = {
    "suggestion": "suggestion",
    "complaint": "complaint",
    "report": "complaint",
    "other": "other",
}


def copy_proposals(apps, schema_editor):
    Proposal = apps.get_model("proposals", "Proposal")
    Feedback = apps.get_model("reviews", "Feedback")
    rows = []
    for p in Proposal.objects.all().iterator():
        status = _STATUS.get(p.status, "closed")
        category = _CATEGORY.get(p.feedback_category or "", "other")
        if category not in ("suggestion", "complaint", "other"):
            category = "other"
        closed = status == "closed"
        rows.append(Feedback(
            id=p.id,
            category=category,
            status=status,
            title=p.title,
            description=p.description or "",
            contact=p.contact or "",
            creator_id=p.creator_id,
            closed_by_id=p.reviewed_by_id if closed else None,
            closed_at=p.reviewed_at if closed else None,
            close_note=(p.reject_reason or "") if closed else "",
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))
    if not rows:
        return
    Feedback.objects.bulk_create(rows)
    _reset_pk_sequence(schema_editor, "reviews_feedback")


def _reset_pk_sequence(schema_editor, table):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                "GREATEST(COALESCE((SELECT MAX(id) FROM reviews_feedback), 1), 1))",
                [table],
            )
        elif connection.vendor == "sqlite":
            cursor.execute("SELECT MAX(id) FROM reviews_feedback")
            max_id = cursor.fetchone()[0] or 0
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = %s", [table])
            if max_id:
                cursor.execute(
                    "INSERT INTO sqlite_sequence (name, seq) VALUES (%s, %s)",
                    [table, max_id],
                )


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0006_feedback_report_models"),
        ("proposals", "0003_alter_proposal_options_remove_proposal_activity_type_and_more"),
    ]

    operations = [
        migrations.RunPython(copy_proposals, migrations.RunPython.noop),
    ]
