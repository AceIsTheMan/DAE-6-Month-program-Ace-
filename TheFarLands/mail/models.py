from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint
from django.utils import timezone

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

    # True only for a Social conversation actually created as a group
    # (see mail.views.mail_group_new) - never set for a 1:1 DM (see
    # _get_or_create_dm), regardless of how many participants a
    # conversation happens to have at any given moment. The member-list
    # sidebar, HOST badge, and "N/10" cap indicator (see mail/templates/
    # mail/index.html) only ever show for a real group - a DM between two
    # people is not treated as a tiny group with a host.
    is_group = models.BooleanField(default=False)

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

    Filing is rate-limited (see mail.views._report_cooldown_remaining):
    3 reports filed by the same reporter within a rolling 48 hours locks
    them out of filing more until the oldest of those 3 ages past 48h.
    """
    BULLYING = 'bullying'
    NSFW = 'nsfw'
    GUIDELINES = 'guidelines'
    PERSONAL_INFO = 'personal_info'
    CATEGORY_CHOICES = [
        (BULLYING, 'Bullying'),
        (NSFW, 'NSFW'),
        (GUIDELINES, 'Profile threatens guidelines'),
        (PERSONAL_INFO, 'Leaking personal information'),
    ]

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
    # Default only matters for the migration itself (this table has never
    # held real data) - every report going forward always sets one
    # explicitly via mail.forms.ReportForm, which has no blank choice.
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=GUIDELINES)
    reason = models.TextField(max_length=1500)
    # Reuses forum's media allowlist/validator, same as Message.media -
    # one attachment per report, same convention as the mail composer.
    media = models.FileField(
        upload_to='reports/media/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=MEDIA_EXTENSIONS)],
    )
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
    Minimum-viable Friend/Block/Mute between two accounts - deliberately
    no request/accept step (instant friend) since nothing else in this
    project has a pending-request notification pattern to extend.

    Block is treated as bidirectional at the permission-check layer (see
    mail.forms._is_blocked_pair) even though the row itself only records
    one direction, so either party blocking the other stops messaging/
    searching between them either way - EXCEPT when either account is a
    moderator (Admin/Director): a block involving a moderator is inert,
    on either side, so a regular account can never wall off a moderator's
    reach (see _is_blocked_pair).

    Mute is one-directional and much narrower than Block: it only
    suppresses the notification badge for messages from the muted
    account (see mail.context_processors.notification_counts) - the
    muted account can still message/find/interact with the muter
    completely normally, nothing is hidden or blocked, their messages
    just don't raise an alert until unmuted.
    """
    FRIEND = 'friend'
    BLOCK = 'block'
    MUTE = 'mute'
    KIND_CHOICES = [
        (FRIEND, 'Friend'),
        (BLOCK, 'Block'),
        (MUTE, 'Mute'),
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


class ModerationAction(models.Model):
    """
    A real, moderator-imposed Mute/Ban/Perm-ban - not to be confused with
    UserRelationship.MUTE (a regular account's own, purely cosmetic
    notification-badge mute). This is enforced site-wide:

      - MUTE blocks the target from posting forum comments and from
        sending anything in Mail/Social (DMs, group messages) - see
        forum.views._require_not_muted_by_moderator and
        mail.views._require_not_muted_by_moderator. It never blocks
        reading.
      - BAN and PERM_BAN block the target from the forum entirely (see
        forum.views._require_not_banned) - the F.R.E.D. block screen
        renders instead of the forum feed. Nothing else on the site is
        restricted by a ban - Home, Mail, and Profile all still work.

    Only Director/Admin accounts can create these (see accounts.models.
    CustomUser.is_moderator), and the Director can never be targeted -
    see mail.forms.ModerationActionForm.

    A target can accumulate a history of these (repeat offenders), so
    "is this account currently muted/banned" is always "is there an
    unlifted, unexpired row of that kind" (see active_for), not a flag
    on CustomUser itself.
    """
    MUTE = 'mute'
    BAN = 'ban'
    PERM_BAN = 'perm_ban'
    KIND_CHOICES = [
        (MUTE, 'Mute'),
        (BAN, 'Ban'),
        (PERM_BAN, 'Permanent Ban'),
    ]

    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='moderation_actions_taken'
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='moderation_actions_received'
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    reason = models.TextField(max_length=1500)
    created_at = models.DateTimeField(auto_now_add=True)

    # Null for PERM_BAN (indefinite, lifted only by hand) and never null
    # for MUTE/BAN, which always have a duration - see mail.forms.
    # ModerationActionForm.
    expires_at = models.DateTimeField(null=True, blank=True)

    # Set when a moderator manually lifts this early (or ends a perm
    # ban) - see mail.views.mail_moderation_lift. A lifted row is never
    # active again even if expires_at hasn't passed yet.
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderation_actions_lifted',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['target', 'kind', 'lifted_at', 'expires_at'])]

    def __str__(self):
        return f'{self.get_kind_display()} on {self.target} by {self.moderator}'

    @property
    def is_active(self):
        if self.lifted_at:
            return False
        if self.expires_at is None:
            return True
        return timezone.now() < self.expires_at

    @classmethod
    def active_for(cls, target, kinds):
        """The most recent still-active row of any of `kinds` against
        `target`, or None - the single query every enforcement check
        (forum views, mail views) runs against."""
        now = timezone.now()
        return (
            cls.objects.filter(target=target, kind__in=kinds, lifted_at__isnull=True)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .order_by('-created_at')
            .first()
        )
