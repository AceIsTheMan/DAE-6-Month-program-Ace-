from collections import defaultdict

from django.db import migrations


def merge_duplicate_dms(apps, schema_editor):
    """One-time data cleanup for a bug in mail.views._get_or_create_dm:
    an annotate()/filter() ordering mistake meant its "does a DM between
    these two already exist" lookup never matched, so every second
    contact between the same pair (a second Friend Request, a Draft,
    a Forward, a Share, ...) silently created a brand new 1:1 Social
    conversation instead of continuing the one already there.

    This merges every such split-up pair back into a single
    conversation: the oldest one survives, every Message from the
    others is reassigned onto it (Message.Meta.ordering is created_at,
    so history still reads in the right order once merged), each
    user's furthest last_read_at carries over, and the now-empty
    duplicates are deleted. Written against historical models via
    apps.get_model, and safe to re-run - a second pass finds no
    duplicate groups left and does nothing.
    """
    Conversation = apps.get_model('mail', 'Conversation')
    ConversationParticipant = apps.get_model('mail', 'ConversationParticipant')
    Message = apps.get_model('mail', 'Message')

    groups = defaultdict(list)
    conversations = Conversation.objects.filter(category='social', is_group=False).prefetch_related('memberships')
    for conversation in conversations:
        participant_ids = frozenset(m.user_id for m in conversation.memberships.all())
        groups[participant_ids].append(conversation)

    for participant_ids, convos in groups.items():
        if len(convos) < 2:
            continue
        convos.sort(key=lambda c: c.created_at)
        canonical = convos[0]
        duplicates = convos[1:]

        for dup in duplicates:
            Message.objects.filter(conversation=dup).update(conversation=canonical)

            for dup_membership in ConversationParticipant.objects.filter(conversation=dup):
                canonical_membership, _ = ConversationParticipant.objects.get_or_create(
                    conversation=canonical, user_id=dup_membership.user_id,
                    defaults={'last_read_at': dup_membership.last_read_at},
                )
                if dup_membership.last_read_at and (
                    not canonical_membership.last_read_at
                    or dup_membership.last_read_at > canonical_membership.last_read_at
                ):
                    canonical_membership.last_read_at = dup_membership.last_read_at
                    canonical_membership.save(update_fields=['last_read_at'])

            if dup.is_admin_only and not canonical.is_admin_only:
                canonical.is_admin_only = True

            dup.delete()

        latest = canonical.messages.order_by('-created_at').first()
        if latest and latest.created_at > canonical.last_message_at:
            canonical.last_message_at = latest.created_at
        canonical.save(update_fields=['is_admin_only', 'last_message_at'])


def noop_reverse(apps, schema_editor):
    """Merged conversations can't be un-split - which duplicate a given
    Message originally belonged to isn't recorded anywhere. Nothing to
    do on a reverse migration."""


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0006_remove_report_report_has_a_target_and_more'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_dms, noop_reverse),
    ]
