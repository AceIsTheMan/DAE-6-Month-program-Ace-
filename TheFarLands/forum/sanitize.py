"""
Turns a forum post/comment body into safe HTML ready to render with the
`safe` filter.

The composer and comment box (see templates/forum/index.html) are plain
<textarea>s - what's typed is exactly what gets saved, so there's no
pasted HTML to allowlist. Instead: the whole body is HTML-escaped first
(so no tag typed or pasted in ever reaches the page as markup), then a
small set of inline markers are turned into the matching safe tag. A
marker never crosses a line break.

    **bold**            -> <b>bold</b>
    __underline__        -> <u>underline</u>
    ~~crossed out~~      -> <s>crossed out</s>
    ||redacted||         -> <span class="redacted-text">redacted</span>
    ==highlighted==      -> <span class="highlight-text">highlighted</span>

Posting is Director-only already, so post bodies always get the markers.
Comments are open to more roles (see forum.views._can_comment), but the
markers themselves stay Director-only there too - `apply_markers=False`
(see forum.views.forum_add_comment_view) skips that step entirely, so
anyone else's ** stays literal, plain, escaped text instead of turning
into <b>.
"""
import re
from html import escape

_MARKERS = [
    (re.compile(r'\*\*([^\n]+?)\*\*'), r'<b>\1</b>'),
    (re.compile(r'__([^\n]+?)__'), r'<u>\1</u>'),
    (re.compile(r'~~([^\n]+?)~~'), r'<s>\1</s>'),
    (re.compile(r'\|\|([^\n]+?)\|\|'), r'<span class="redacted-text">\1</span>'),
    (re.compile(r'==([^\n]+?)=='), r'<span class="highlight-text">\1</span>'),
]

# @mention linking - shared by mail (mail.templatetags.mail_extras) and
# forum (forum.templatetags.forum_extras) so there's exactly one place
# that decides what counts as a mention token and what "glows red" means.
_MENTION_RE = re.compile(r'@(\w+)')
_TAG_OR_ENTITY_RE = re.compile(r'(<[^>]+>|&[a-zA-Z0-9#]+;)')


def linkify_mentions(html_text):
    """Turn `@username` into a link to that account's profile, but ONLY
    when `username` resolves to a real, existing account (exact case
    match - the autocomplete that inserts a mention already gets the
    casing right, so this doesn't need to be case-insensitive too). A
    non-matching `@word` is left as inert plain text - no link, no
    styling, same as any other word.

    Must run on already-sanitized HTML (see sanitize_post_html above) and
    only ever rewrites plain-text runs - splits on the same tag/entity
    pattern forum.templatetags.forum_extras.highlight already uses for
    exactly this reason, so it never rewrites text that's already inside
    a tag (e.g. a ||redacted||/==highlighted== span's own markup).
    """
    if not html_text or '@' not in html_text:
        return html_text or ''
    # Local import - forum.sanitize is imported at Django app-loading time
    # by mail.models (for MEDIA_EXTENSIONS) and accounts has no reverse
    # dependency on forum, so this is safe, but importing accounts.models
    # at module level here would make forum depend on accounts loading
    # first for no benefit beyond this one function.
    from django.urls import reverse

    from accounts.models import CustomUser

    parts = _TAG_OR_ENTITY_RE.split(html_text)
    tokens = set()
    for i in range(0, len(parts), 2):
        tokens.update(m.group(1) for m in _MENTION_RE.finditer(parts[i]))
    if not tokens:
        return html_text

    real_usernames = set(CustomUser.objects.filter(username__in=tokens).values_list('username', flat=True))
    if not real_usernames:
        return html_text

    def repl(m):
        token = m.group(1)
        if token not in real_usernames:
            return m.group(0)
        return f'<a href="{reverse("user_profile", args=[token])}" class="mention-valid">@{escape(token)}</a>'

    for i in range(0, len(parts), 2):
        parts[i] = _MENTION_RE.sub(repl, parts[i])
    return ''.join(parts)


def sanitize_post_html(raw_text, apply_markers=True):
    """Escape raw_text, apply the marker substitutions above (unless
    apply_markers=False), and turn newlines into <br>."""
    if not raw_text:
        return ''
    text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    text = escape(text)
    if apply_markers:
        for pattern, replacement in _MARKERS:
            text = pattern.sub(replacement, text)
    return text.replace('\n', '<br>')
