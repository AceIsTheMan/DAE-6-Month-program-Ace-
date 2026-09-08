from .models import Conversation, ConversationParticipant, UserRelationship


def notification_counts(request):
    """
    Injects `unread_mail_count`, `unread_directive_count`, and
    `currency_balance` into every template's context - this is the one
    place in the project it's worth introducing a context processor
    (a first here) rather than threading these through every existing
    view in accounts and forum, since the nav (accounts/templates/
    base.html, duplicated in home.html) renders on every page.

    A conversation counts as unread if it has at least one Message,
    created after this user's last_read_at (or ever, if never read),
    from someone OTHER than a muted account (see mail.models.
    UserRelationship's docstring on Mute - it only suppresses this
    badge, nothing else). Views bump last_read_at both when a user opens
    a thread AND when they send into it (see mail.views), so a
    conversation where this user is the only sender never shows unread.

    This is a Python loop over the user's own conversations (one query
    per conversation), not a single aggregate query - simplest way to
    apply the per-sender mute filter per conversation without a gnarlier
    ORM expression, and fine at this project's scale (a handful of
    conversations per user).
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_guest:
        return {}

    muted_ids = set(
        UserRelationship.objects.filter(from_user=user, kind=UserRelationship.MUTE).values_list('to_user_id', flat=True)
    )

    memberships = ConversationParticipant.objects.filter(user=user).select_related('conversation')
    unread_mail_count = 0
    unread_directive_count = 0
    for membership in memberships:
        conversation = membership.conversation
        unread_messages = conversation.messages.exclude(sender=user)
        if muted_ids:
            unread_messages = unread_messages.exclude(sender_id__in=muted_ids)
        if membership.last_read_at:
            unread_messages = unread_messages.filter(created_at__gt=membership.last_read_at)
        if unread_messages.exists():
            unread_mail_count += 1
            if conversation.category == Conversation.DIRECTIVE:
                unread_directive_count += 1

    return {
        'unread_mail_count': unread_mail_count,
        'unread_directive_count': unread_directive_count,
        'currency_balance': user.currency,
    }
