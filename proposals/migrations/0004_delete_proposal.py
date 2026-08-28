from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0003_alter_proposal_options_remove_proposal_activity_type_and_more"),
        ("attachments", "0006_attachment_feedback"),
        ("reviews", "0007_copy_proposals_to_feedback"),
    ]

    operations = [
        migrations.DeleteModel(name="Proposal"),
    ]
