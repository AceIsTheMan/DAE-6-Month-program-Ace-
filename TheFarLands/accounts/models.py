from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    """
    Custom User Model for The Far Lands Project.
    Inherits from AbstractUser to keep default auth features.
    """

    # Moderation role hierarchy, lowest to highest. "Director" sits above
    # Hacker (guest accounts), Agent (regular accounts) and Admin - it's
    # the site owner's role, meant for a single account, and takes first
    # priority over every other role when permissions are checked.
    ROLE_HACKER = 'Hacker'
    ROLE_AGENT = 'Agent'
    ROLE_ADMIN = 'Admin'
    ROLE_DIRECTOR = 'Director'
    ROLE_HIERARCHY = [ROLE_HACKER, ROLE_AGENT, ROLE_ADMIN, ROLE_DIRECTOR]
    ROLE_CHOICES = [(r, r) for r in ROLE_HIERARCHY]

    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    rank = models.CharField(max_length=50, default='Newbie')
    alias = models.CharField(max_length=12, blank=True)

    # Moderation role - separate from `rank` (which is just a flavor label
    # shown on the profile dossier, e.g. "Newbie"). Guest accounts default
    # to Hacker at signup (see accounts.views), everyone else starts as
    # Agent; Admin/Director are granted manually.
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default=ROLE_AGENT)

    # Guest ("Hacker") accounts: registered with just a codename + password
    # (see GuestRegisterForm), limited to a short trial and auto-deleted
    # once it's up (see accounts.middleware.GuestExpiryMiddleware), and
    # blocked from setting a profile picture (see ProfileEditForm).
    is_guest = models.BooleanField(default=False)

    # Email verification for regular (non-guest) accounts. Defaults to True
    # so guests and superusers (created via createsuperuser) are never
    # affected - RegisterForm.save() is the one place that sets this False,
    # for a normal registration, until the emailed link is clicked (see
    # accounts.views.verify_email_view). Deliberately a separate flag from
    # is_active: Django's own authenticate() already refuses inactive
    # users before a login form ever gets a chance to show a custom
    # message, so this needed its own field to give a clear "verify your
    # email" error instead of a generic "wrong password" one.
    email_verified = models.BooleanField(default=True)

    GUEST_TRIAL_DAYS = 7

    @property
    def guest_expires_at(self):
        """When this guest account will be auto-deleted, or None for a
        regular (non-guest) account."""
        if not self.is_guest or not self.date_joined:
            return None
        return self.date_joined + timezone.timedelta(days=self.GUEST_TRIAL_DAYS)

    @property
    def guest_days_left(self):
        """Whole days left on a guest account's trial (0 once it's past
        due but hasn't been cleaned up yet), or None for a regular
        account."""
        expires_at = self.guest_expires_at
        if expires_at is None:
            return None
        return max(0, (expires_at - timezone.now()).days)

    @property
    def is_director(self):
        """True for the site owner's account - the top of ROLE_HIERARCHY,
        outranking every Hacker/Agent/Admin."""
        return self.role == self.ROLE_DIRECTOR

    def __str__(self):
        return self.username


class GuestArchive(models.Model):
    """
    A frozen snapshot of a guest ("Hacker") account, taken the moment
    before accounts.middleware.GuestExpiryMiddleware deletes it for real
    once its 7-day trial runs out. The account itself is gone - username
    freed up, login dead, everything CASCADE-linked to it removed (their
    reactions, etc.) - but this row is the record that they existed:
    who they were, when they were here, and how much they did with it.

    Never updated after creation, and never linked back to a live
    CustomUser (there isn't one anymore) - purely historical, viewable in
    the Django admin (see accounts.admin.GuestArchiveAdmin).
    """
    original_user_id = models.PositiveIntegerField(
        help_text='The id the account had before it was deleted - not a live foreign key.'
    )
    username = models.CharField(max_length=150)
    alias = models.CharField(max_length=12, blank=True)
    rank = models.CharField(max_length=50)
    bio = models.TextField(max_length=500, blank=True)
    # Just the storage path, not a live ImageField - Django never deletes
    # the actual file on model delete, so the picture itself survives on
    # disk even though nothing else points to it anymore. This is the
    # pointer back to it.
    profile_picture_path = models.CharField(max_length=255, blank=True)
    date_joined = models.DateTimeField()
    last_login = models.DateTimeField(null=True, blank=True)
    reaction_count = models.PositiveIntegerField(
        default=0, help_text='How many forum reactions they had at the moment of expiry.'
    )
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-archived_at']

    def __str__(self):
        return f'{self.username} (expired {self.archived_at:%Y-%m-%d})'
