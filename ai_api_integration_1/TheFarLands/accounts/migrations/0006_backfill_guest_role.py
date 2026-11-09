# Backfill role='Hacker' for existing guest accounts, since the new
# `role` field (added in 0005) defaults everyone to 'Agent' - without
# this, existing guests would show as AGENT on their profile instead of
# HACKER until they happened to re-save.

from django.db import migrations


def set_hacker_role_for_guests(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.filter(is_guest=True).update(role='Hacker')


def reverse_noop(apps, schema_editor):
    # Nothing sensible to reverse to - role stays as-is.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_customuser_role'),
    ]

    operations = [
        migrations.RunPython(set_hacker_role_for_guests, reverse_noop),
    ]
