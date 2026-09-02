from django import template

register = template.Library()


@register.filter
def dict_get(mapping, key):
    """Look up `key` in a dict from the template - Django's `.` lookup
    can't take a variable as the key, so `my_reactions|dict_get:post.id`
    stands in for `my_reactions[post.id]` (see forum/views.py, where
    my_reactions maps post id -> the current user's reaction value)."""
    if not mapping:
        return None
    return mapping.get(key)
