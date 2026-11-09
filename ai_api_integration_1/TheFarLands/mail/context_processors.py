from collections import Counter

from django.db.models import DateTimeField, Exists, OuterRef, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Conversation, ConversationParticipant, Message, UserRelationship

#: Stand-in for "never read" when building the unread Exists subquery below -
#: any real Message.created_at will be after this, so Coalescing a null
#: last_read_at down to this sentinel is equivalent to not filtering by
#: created_at at all (see notification_counts).
_NEVER_READ_SENTINEL = timezone.datetime(1970, 1, 1, tzinfo=timezone.UTC)


def notification_counts(request):
    """
    Injects `unread_mail_count`, `unread_directive_count`,
    `unread_by_category`, and `currency_balance` into every template's
    context - this is the one place in the project it's worth
    introducing a context processor (a first here) rather than
    threading these through every existing view in accounts and forum,
    since the nav (accounts/templates/base.html, duplicated in
    home.html) renders on every page.

    `unread_by_category` breaks the same underlying count down by
    Conversation.category (e.g. {'social': 2, 'fan_letter': 1}) so the
    Mail sidebar (mail/templates/mail/_sidebar.html) can badge Social/
    Updates/Fan Letter individually instead of only surfacing one
    combined number - Inbox generalizes every category into one feed
    (see mail.views.mail_inbox), so without a per-category breakdown
    there was no way to tell where an unread notification actually was
    without opening Inbox and reading every row.

    A conversation counts as unread if it has at least one Message,
    created after this user's last_read_at (or ever, if never read),
    from someone OTHER than a muted account (see mail.models.
    UserRelationship's docstring on Mute - it only suppresses this
    badge, nothing else). Views bump last_read_at both when a user opens
    a thread AND when they send into it (see mail.views), so a
    conversation where this user is the only sender never shows unread.

    A single annotated query (one Exists subquery per membership, all
    evaluated in one round trip) instead of a Python loop issuing one
    `.exists()` query per conversation - this ran on every page load, so
    a user in N conversations used to cost N+1 queries just for the nav.

    `mail_cutscene_mode` (Settings tab, Cutscenes sub-tab) also rides
    along here since it's another per-request, every-page value the Mail
    tab's boot-up terminal script (mail/templates/mail/index.html) needs
    - same "one context processor, not threaded through every view"
    rationale as everything else in this function. If Notifications is
    turned off (CustomUser.notifications_enabled), the unread counts
    short-circuit to zero without even running the membership query -
    there's nothing to show, so there's nothing to compute either.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_guest:
        return {}

    if not user.notifications_enabled:
        return {
            'unread_mail_count': 0,
            'unread_directive_count': 0,
            'unread_by_category': {},
            'currency_balance': user.currency,
            'mail_cutscene_mode': user.mail_cutscene_mode,
        }

    muted_ids = set(
        UserRelationship.objects.filter(from_user=user, kind=UserRelationship.MUTE).values_list('to_user_id', flat=True)
    )

    unread_since = Coalesce(OuterRef('last_read_at'), Value(_NEVER_READ_SENTINEL, output_field=DateTimeField()))
    unread_messages = Message.objects.filter(
        conversation=OuterRef('conversation_id'), created_at__gt=unread_since
    ).exclude(sender=user)
    if muted_ids:
        unread_messages = unread_messages.exclude(sender_id__in=muted_ids)

    memberships = (
        ConversationParticipant.objects.filter(user=user)
        .select_related('conversation')
        .annotate(is_unread=Exists(unread_messages))
    )
    unread_by_category = Counter()
    for membership in memberships:
        if membership.is_unread:
            unread_by_category[membership.conversation.category] += 1

    return {
        'unread_mail_count': sum(unread_by_category.values()),
        'unread_directive_count': unread_by_category[Conversation.DIRECTIVE],
        'unread_by_category': unread_by_category,
        'currency_balance': user.currency,
        'mail_cutscene_mode': user.mail_cutscene_mode,
    }
