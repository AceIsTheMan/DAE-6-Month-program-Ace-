from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import models


def _youtube_id(url):
    """Pull the video id out of a youtube.com/watch, youtu.be/, or
    youtube.com/embed/ URL, or None if it isn't a YouTube link."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    if host == 'youtu.be':
        return parsed.path.lstrip('/').split('/')[0] or None
    if host.endswith('youtube.com'):
        if parsed.path == '/watch':
            values = parse_qs(parsed.query).get('v')
            return values[0] if values else None
        if parsed.path.startswith('/embed/'):
            return parsed.path[len('/embed/'):].split('/')[0] or None
    return None


class Post(models.Model):
    """
    A forum post - currently a one-way broadcast board: posting is
    restricted to the Director role (see forum.views.forum_index_view
    and accounts.models.CustomUser.is_director), everyone else just reads
    the feed.
    """
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_posts')
    created_at = models.DateTimeField(auto_now_add=True)

    # Rich text body - sanitized HTML (see forum.sanitize.sanitize_post_html),
    # limited to the composer's own formatting: bold, underline, strike-
    # through, redacted, highlight, line breaks, and plain links.
    body = models.TextField(blank=True)

    image = models.ImageField(upload_to='forum_posts/images/', blank=True, null=True)

    # Video is a URL, not an upload - keeps this simple (YouTube links or
    # a direct .mp4/.webm link) without needing to store/transcode large
    # files server-side.
    video_url = models.URLField(blank=True)

    link_url = models.URLField(blank=True)
    link_label = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Post #{self.pk} by {self.author}'

    @property
    def youtube_id(self):
        return _youtube_id(self.video_url) if self.video_url else None

    @property
    def video_embed_url(self):
        """A YouTube URL safe to embed in an <iframe> (built from an id we
        extracted ourselves, never the raw stored URL), or None - in which
        case video_url is rendered as a direct <video src> instead."""
        vid = self.youtube_id
        return f'https://www.youtube.com/embed/{vid}' if vid else None
