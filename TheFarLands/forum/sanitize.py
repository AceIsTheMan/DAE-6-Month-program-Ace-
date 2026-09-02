"""
Turns a forum post body into safe HTML ready to render with the `safe`
filter.

The composer (see templates/forum/index.html) is a plain <textarea> now,
not a contenteditable rich-text box - what the poster types is exactly
what gets saved, so there's no pasted HTML to allowlist. Instead: the
whole body is HTML-escaped first (so no tag typed or pasted in ever
reaches the page as markup), then a small set of inline markers are
turned into the matching safe tag. A marker never crosses a line break.

    **bold**            -> <b>bold</b>
    __underline__        -> <u>underline</u>
    ~~crossed out~~      -> <s>crossed out</s>
    ||redacted||         -> <span class="redacted-text">redacted</span>
    ==highlighted==      -> <span class="highlight-text">highlighted</span>
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


def sanitize_post_html(raw_text):
    """Escape raw_text, apply the marker substitutions above, and turn
    newlines into <br>."""
    if not raw_text:
        return ''
    text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    text = escape(text)
    for pattern, replacement in _MARKERS:
        text = pattern.sub(replacement, text)
    return text.replace('\n', '<br>')
