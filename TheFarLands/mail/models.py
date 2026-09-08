from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint

from forum.models import MEDIA_EXTENSIONS, VIDEO_EXTENSIONS, Post


class Conversation(models.Model):
    """
    A single unifying container for every kind of mail thread: a Social
    1:1 DM, a Social group chat, a Director "Update" announcement, and a
    Director "Directive" - all just a Conversation with a different
    `category` and participant count, rather than four separate models.

    This is what makes the Mail tab's Inbox ("all categories generalized"
    - see mail.views.mail_inbox) a single query across one Message table
    instead of a union across several unrelated tables.

    - A Social DM is a SOCIAL conversation with exactly 2 participants.
    - A Social group is a SOCIAL conversation with 3-10 participants
      (cap enforced in mail.forms.GroupCreateForm, not the DB - SQLite has
      no easy row-count CHECK across a many-to-many).
    - An UPDATE conversation is Director-authored, read-only for
      recipients (see mail.views.mail_updates) - no reply endpoint exists.
    - A DIRECTIVE conversation is one Director-to-recipient(s) send (see
      mail.views.mail_directive_new) - like UPDATE, no reply endpoint
      exists, and unlike everything else in this model, there is also no
      delete/dismiss endpoint anywhere for it. That absence is the entire
      mechanism behind "cannot be replied, cannot be ignored either."
    """
    SOCIAL = 'social'
    UPDATE = 'update'
    DIRECTIVE = 'directive'
    CATEGORY_CHOICES = [
        (SOCIAL, 'Social'),
        (UPDATE, 'Update'),
        (DIRECTIVE, 'Directive'),
    ]

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)

    # The Social group's host, or the Director who sent an Update/
    # Directive. For a 1:1 DM this is whoever happened to start it - not
    # meaningfully "in charge" of anything, just who gets no special
    # treatment either since DMs have no host badge.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mail_conversations_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Denormalized, bumped by mail.views whenever a Message is added -
    # lets Inbox/Sent/Social thread lists sort without a join+aggregate
    # on every request.
    last_message_at = models.DateTimeField(auto_now_add=True)

    # Optional label, only meaningful for Social groups (see
    # mail.forms.GroupCreateForm) - blank for DMs/Updates/Directives.
    title = models.CharField(max_length=60, blank=True)

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='ConversationParticipant', related_name='mail_conversations'
    )

    class Meta:
        ordering = ['-last_message_at']
        indexes = [models.Index(fields=['category', 'last_message_at'])]

    def __str__(self):
        return f'{self.get_category_display()} conversation #{self.pk}'


class ConversationParticipant(models.Model):
    """
    Through-row for Conversation.participants - who's in a thread, and
    where they've read up to. `is_host` is deliberately not a stored
    field: it's derived as `conversation.created_by_id == user_id`
    (see Conversation.created_by) so there's only one source of truth for
    who's hosting a group.
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mail_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    # Bumped to now() when this user opens the thread (see
    # mail.views.mail_social_thread) - drives the unread badge/highlight.
    # Deliberately separate from "can this be dismissed": marking a
    # Directive/Update read is fine, deleting it is not - see
    # Conversation's docstring.
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['conversation', 'user'], name='one_participant_row_per_user'),
        ]

    def __str__(self):
        return f'{self.user} in conversation #{self.conversation_id}'


class Message(models.Model):
    """
    One message in a Conversation. Body formatting reuses
    forum.sanitize.sanitize_post_html exactly as-is - no second
    sanitizer for this project to maintain. Unlike forum.models.Comment
    (which only enforces its character cap via the widget's HTML
    `maxlength`), the 800-char cap here is enforced server-side too, in
    mail.forms.MessageComposeForm.clean_body.
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mail_messages_sent')
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Reuses forum's exact media extension allowlist (see forum.models.
    # MEDIA_EXTENSIONS) instead of a second, potentially-drifting list -
    # mail already depends on forum for `shared_post` below.
    media = models.FileField(
        upload_to='mail_messages/media/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=MEDIA_EXTENSIONS)],
    )

    # A GIF picked from the Tenor search (see mail.views.mail_gif_search)
    # - only the stable CDN URL is ever stored, never the binary.
    gif_url = models.URLField(blank=True)

    # Set when this message is a forum post shared into Mail (see
    # mail.views.mail_forum_share). SET_NULL (not CASCADE) on purpose: if
    # the Director later deletes the original post, the mail message
    # survives and the template just renders "This post is no longer
    # available" instead of the share vanishing outright.
    shared_post = models.ForeignKey(
        Post, on_delete=models.SET_NULL, null=True, blank=True, related_name='mail_shares'
    )

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['conversation', 'created_at'])]

    def __str__(self):
        return f'Message #{self.pk} from {self.sender} in conversation #{self.conversation_id}'

    @property
    def media_is_video(self):
        """Same check as forum.models.Post.media_is_video - whether
        `media` should render with <video> instead of <img>."""
        if not self.media:
            return False
        ext = self.media.name.rsplit('.', 1)[-1].lower()
        return ext in VIDEO_EXTENSIONS


class Report(models.Model):
    """
    A moderation report - filed by any authenticated account, including
    guests (reporting is a safety valve, not a privilege gated the same
    way Social/Mail participation is), reviewed only by Director/Admin
    (see accounts.models.CustomUser.is_moderator and
    mail.views.mail_reports).

    Targets either a specific Message or a user in general (from their
    profile page) - at least one of the two is required, enforced both at
    the DB layer (CheckConstraint below) and in mail.forms.ReportForm.
    """
    OPEN = 'open'
    RESOLVED = 'resolved'
    DISMISSED = 'dismissed'
    STATUS_CHOICES = [
        (OPEN, 'Open'),
        (RESOLVED, 'Resolved'),
        (DISMISSED, 'Dismissed'),
    ]

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_filed')
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_against'
    )
    reported_message = models.ForeignKey(
        Message, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports'
    )
    reason = models.TextField(max_length=800)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_resolved',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'created_at'])]
        constraints = [
            CheckConstraint(
                condition=Q(reported_user__isnull=False) | Q(reported_message__isnull=False),
                name='report_has_a_target',
            ),
        ]

    def __str__(self):
        return f'Report #{self.pk} by {self.reporter} ({self.get_status_display()})'


class UserRelationship(models.Model):
    """
    Minimum-viable Friend/Block between two accounts - deliberately no
    request/accept step (instant friend) since nothing else in this
    project has a pending-request notification pattern to extend. A
    block is treated as bidirectional at the permission-check layer (see
    mail.views._is_blocked_pair) even though the row itself only records
    one direction, so either party blocking the other stops messaging
    between them either way.
    """
    FRIEND = 'friend'
    BLOCK = 'block'
    KIND_CHOICES = [
        (FRIEND, 'Friend'),
        (BLOCK, 'Block'),
    ]

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='relationships_initiated'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='relationships_received'
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['from_user', 'to_user', 'kind'], name='one_relationship_kind_per_pair'),
            CheckConstraint(condition=~Q(from_user=models.F('to_user')), name='no_self_relationship'),
        ]

    def __str__(self):
        return f'{self.from_user} {self.kind}s {self.to_user}'
