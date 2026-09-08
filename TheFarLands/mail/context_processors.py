from django.db.models import F, Q

from .models import Conversation, ConversationParticipant


def notification_counts(request):
    """
    Injects `unread_mail_count`, `unread_directive_count`, and
    `currency_balance` into every template's context - this is the one
    place in the project it's worth introducing a context processor
    (a first here) rather than threading these through every existing
    view in accounts and forum, since the nav (accounts/templates/
    base.html, duplicated in home.html) renders on every page.

    "Unread" = a ConversationParticipant row whose last_read_at is either
    null or older than the conversation's last_message_at. Views bump
    last_read_at both when a user opens a thread AND when they send into
    it (see mail.views), so a conversation where this user is the only
    sender never shows as unread for them.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_guest:
        return {}

    unread = ConversationParticipant.objects.filter(user=user).filter(
        Q(last_read_at__isnull=True) | Q(last_read_at__lt=F('conversation__last_message_at'))
    )

    return {
        'unread_mail_count': unread.count(),
        'unread_directive_count': unread.filter(conversation__category=Conversation.DIRECTIVE).count(),
        'currency_balance': user.currency,
    }
