"""
Minimal allowlist HTML sanitizer for forum post bodies.

The composer (see templates/forum/index.html) only ever produces a small,
known set of inline markup - bold/underline/strikethrough, the custom
redacted/highlight spans, line breaks, and plain links - via its own
toolbar, never a general "paste anything" rich text editor. This still
runs server-side on every save (never trust the client): it strips
anything outside that allowlist rather than trying to "fix" it.
"""
from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {'b', 'strong', 'u', 's', 'span', 'br', 'a'}
ALLOWED_SPAN_CLASSES = {'redacted-text', 'highlight-text'}
ALLOWED_LINK_SCHEMES = ('http://', 'https://', 'mailto:')
# Tags whose *content* gets dropped outright (not just unwrapped) - never
# let raw script/style text reach the page, even as inert visible text.
DROP_CONTENT_TAGS = {'script', 'style'}


class _PostBodySanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._drop_depth = 0
        # One entry per *real* open tag, in document order: the tag name
        # we actually emitted for it, or None if it was unwrapped/dropped.
        # Lets handle_endtag close only what handle_starttag actually opened.
        self._stack = []

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, self_closing=True)

    def _open(self, tag, attrs, self_closing):
        if tag in DROP_CONTENT_TAGS:
            self._drop_depth += 1
            if not self_closing:
                self._stack.append(None)
            return
        if self._drop_depth:
            if not self_closing:
                self._stack.append(None)
            return

        emitted = None
        attrs = dict(attrs)
        if tag == 'span':
            cls = ' '.join(c for c in (attrs.get('class') or '').split() if c in ALLOWED_SPAN_CLASSES)
            if cls:
                self.out.append(f'<span class="{cls}">')
                emitted = 'span'
        elif tag == 'a':
            href = (attrs.get('href') or '').strip()
            if href.startswith(ALLOWED_LINK_SCHEMES):
                self.out.append(f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer nofollow">')
                emitted = 'a'
        elif tag == 'br':
            self.out.append('<br>')
            # void element - nothing pushed below, regardless of self_closing
        elif tag in ALLOWED_TAGS:
            self.out.append(f'<{tag}>')
            emitted = tag
        # anything else: unwrap (drop the tag, its text still comes through
        # handle_data)

        if tag != 'br' and not self_closing:
            self._stack.append(emitted)

    def handle_endtag(self, tag):
        if self._drop_depth:
            if tag in DROP_CONTENT_TAGS:
                self._drop_depth -= 1
            if self._stack:
                self._stack.pop()
            return
        if tag == 'br':
            return
        emitted = self._stack.pop() if self._stack else None
        if emitted:
            self.out.append(f'</{emitted}>')

    def handle_data(self, data):
        if self._drop_depth:
            return
        self.out.append(escape(data))

    def get_output(self):
        return ''.join(self.out)


def sanitize_post_html(raw_html):
    """Strip raw_html down to the allowlist above and return safe HTML,
    ready to render with the `safe` filter."""
    if not raw_html:
        return ''
    parser = _PostBodySanitizer()
    parser.feed(raw_html)
    parser.close()
    return parser.get_output()
