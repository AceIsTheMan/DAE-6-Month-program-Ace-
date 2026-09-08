from django import template

register = template.Library()


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
