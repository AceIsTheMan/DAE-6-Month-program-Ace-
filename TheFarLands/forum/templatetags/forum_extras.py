import re

from django import template
from django.utils.safestring import mark_safe

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


# Matches an HTML tag or a character reference (&amp; &#39; etc.) - the
# two things a naive substring search must never reach into. Everything
# between them is plain post text, safe to search and wrap.
_SKIP_RE = re.compile(r'(<[^>]+>|&[a-zA-Z0-9#]+;)')


@register.filter
def highlight(html_text, query):
    """Wrap every case-insensitive occurrence of `query` in the visible
    text of `html_text` with <mark>, for the forum search bar (see
    forum.views.forum_index_view). `html_text` is assumed to already be
    sanitized, safe HTML (see forum.sanitize.sanitize_post_html) - this
    only ever inserts a fixed <mark> tag around existing text, so the
    result is still safe to render with `|safe`."""
    if not html_text or not query:
        return html_text
    query = query.strip()
    if not query:
        return html_text

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    parts = _SKIP_RE.split(html_text)
    for i, part in enumerate(parts):
        if part.startswith('<') or part.startswith('&'):
            continue
        parts[i] = pattern.sub(
            lambda m: '<mark class="search-hit">' + m.group(0) + '</mark>', part
        )
    return mark_safe(''.join(parts))
