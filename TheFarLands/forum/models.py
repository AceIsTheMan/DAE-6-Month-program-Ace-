from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

# Extensions the "Image" upload accepts. The composer label stays "Image"
# (see forum.forms.PostForm / templates/forum/index.html) but the field
# takes either an image or a short video uploaded straight from the
# poster's computer - there's no separate "video" upload.
IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
VIDEO_EXTENSIONS = ['mp4', 'webm', 'mov', 'ogg']
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS


class Post(models.Model):
    """
    A forum post - currently a one-way broadcast board: posting is
    restricted to the Director role (see forum.views.forum_index_view
    and accounts.models.CustomUser.is_director), the site's sole
    Director/Developer account. Everyone else just reads the feed and
    can react with a like or dislike (see PostReaction below).
    """
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_posts')
    created_at = models.DateTimeField(auto_now_add=True)

    # Set only by forum.views.forum_edit_post_view, never shown to anyone
    # but the Director (see templates/forum/index.html) - an edited post
    # looks identical to an unedited one for every other role.
    edited_at = models.DateTimeField(null=True, blank=True)

    # Rich text body - sanitized HTML (see forum.sanitize.sanitize_post_html),
    # limited to the composer's own formatting: bold, underline, strike-
    # through, redacted, highlight, line breaks, and plain links.
    body = models.TextField(blank=True)

    # Uploaded straight from the poster's computer: an image or a short
    # video file. Still labeled "Image" in the composer to keep the form
    # simple, but accepts either - see media_is_video below for which one
    # a given post has.
    media = models.FileField(
        upload_to='forum_posts/media/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=MEDIA_EXTENSIONS)],
    )

    # A general link, not restricted to any one site - may point to
    # footage hosted elsewhere (YouTube, etc.) or anything worth sharing.
    # Always rendered as a plain outbound button, never embedded.
    link_url = models.URLField(blank=True)
    link_label = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Post #{self.pk} by {self.author}'

    @property
    def media_is_video(self):
        """Whether `media` should render with <video> instead of <img>."""
        if not self.media:
            return False
        ext = self.media.name.rsplit('.', 1)[-1].lower()
        return ext in VIDEO_EXTENSIONS

    @property
    def like_count(self):
        return self.reactions.filter(value=PostReaction.LIKE).count()

    @property
    def dislike_count(self):
        return self.reactions.filter(value=PostReaction.DISLIKE).count()


class PostReaction(models.Model):
    """
    One like or dislike from one user on one post (see
    forum.views.forum_react_view). A user has at most one reaction per
    post: reacting the same way again clears it, reacting the other way
    flips it. Open to anyone signed in - reacting isn't Director-gated,
    only posting is.
    """
    LIKE = 'like'
    DISLIKE = 'dislike'
    VALUE_CHOICES = [(LIKE, 'Like'), (DISLIKE, 'Dislike')]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_reactions')
    value = models.CharField(max_length=7, choices=VALUE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['post', 'user'], name='one_reaction_per_user_per_post'),
        ]

    def __str__(self):
        return f'{self.user} {self.value}s Post #{self.post_id}'


class Comment(models.Model):
    """
    A comment on a Post. Open to every signed-in account except guest
    ("Hacker") accounts - see forum.views._can_comment - unlike reactions,
    which are open to any signed-in user. Plain text, run through the
    same marker-based formatting as post bodies (see forum.sanitize), no
    media/link attachments.
    """
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_comments')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Oldest first - the comment section loads forward in time as you
        # scroll and ask for more (see forum.views.forum_comments_view),
        # like reading a conversation from the start.
        ordering = ['created_at']

    def __str__(self):
        return f'Comment #{self.pk} by {self.author} on Post #{self.post_id}'
