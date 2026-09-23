import re

from django import template
from django.utils.safestring import mark_safe

from forum.sanitize import linkify_mentions

register = template.Library()

_WORD_RE = re.compile(r'\S+')


def _redact_html(html_text):
    """Word-shaped blackout bars in place of real text, whitespace/<br>
    breaks preserved - "spaces where words are supposed to be" (see
    Conversation.is_admin_only's docstring). Message bodies are already-
    sanitized plain text with only <br> tags in them (see forum.sanitize.
    sanitize_post_html), so a plain split on <br> is enough - there's
    nothing else to walk around."""
    if not html_text:
        return ''
    parts = html_text.split('<br>')
    return '<br>'.join(_WORD_RE.sub(lambda m: '█' * len(m.group(0)), part) for part in parts)


@register.filter
def render_body(message, viewer):
    """The message body actually safe to render for `viewer` - real
    content (with @mentions linkified) if this isn't confidential Director
    <->Admin mail or `viewer` is authorized to see it (see
    accounts.models.CustomUser.is_moderator), a word-shaped blackout
    otherwise. Redaction happens BEFORE any linkifying could apply, not
    after, so there's no risk of a mention link's own <a> markup getting
    chewed up by the blackout substitution."""
    if message.is_admin_only and not (viewer.is_authenticated and viewer.is_moderator):
        return mark_safe(_redact_html(message.body))
    return mark_safe(linkify_mentions(message.body))


@register.filter
def ne(a, b):
    """`a != b` as a filter - {% include %}'s `with` clause only accepts
    variables/filter expressions, not inline comparisons, so this (and
    `eq` below) is how a boolean built from a comparison gets passed
    through an include, e.g. show_friend=message.sender_id|ne:user.id."""
    return a != b


@register.filter
def eq(a, b):
    """See `ne` above - the same need, the other direction."""
    return a == b


@register.filter
def warn_sender_display(message, viewer):
    """The sender name to show for this message - masked to "Moderation
    Team" when it's the undeletable Directive delivering a Report-flow
    Warning (see mail.models.Warning, source=REPORT) and `viewer` isn't
    the Director. The real sender is still stored in the DB either way -
    only the Director can trace who actually sent it (see the Dashboard's
    Admin Logs panel)."""
    warning = getattr(message, 'warning', None)
    if warning and warning.source == 'report' and not (viewer.is_authenticated and viewer.is_director):
        return 'Moderation Team'
    return message.sender.username


@register.filter
def can_delete_message(message, viewer):
    """Whether `viewer` may soft-delete this message - see
    mail.views.mail_message_delete. Never true for a DIRECTIVE (no
    delete route exists for that category anywhere, on purpose)."""
    if not viewer.is_authenticated or message.conversation.category == 'directive':
        return False
    return message.sender_id == viewer.pk or viewer.is_moderator


@register.filter
def admin_only_media_blocked(message, viewer):
    """Whether `viewer` must see a solid blackout box instead of this
    message's real image/video - see mail.views.mail_message_media for
    why the underlying file is ALSO gated at the serving layer, not just
    hidden here (a template-only block is cosmetic; the raw MEDIA_URL
    would still work if guessed)."""
    return bool(message.is_admin_only and not (viewer.is_authenticated and viewer.is_moderator))


@register.filter
def conversation_display_name(conversation, viewer):
    """What to show as a Social conversation's name/title.

    A real group (see mail.models.Conversation.is_group) shows its title,
    or "Group Chat" if none was set. A 1:1 DM has no host/title concept
    at all - it just shows the other participant's username, not a
    generic "Direct Message" label, since a DM between two individuals
    isn't a group of one host + one member."""
    if conversation.is_group:
        return conversation.title or 'Group Chat'
    other = conversation.memberships.exclude(user=viewer).select_related('user').first()
    return other.user.username if other else 'Direct Message'


@register.filter
def dm_partner(conversation, viewer):
    """The other account in a 1:1 DM (for showing their profile picture
    next to their name in the conversation header) - None for a group,
    where there's no single "other person" to show."""
    if conversation.is_group:
        return None
    membership = conversation.memberships.exclude(user=viewer).select_related('user').first()
    return membership.user if membership else None
