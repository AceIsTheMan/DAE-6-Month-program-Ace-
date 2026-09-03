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
