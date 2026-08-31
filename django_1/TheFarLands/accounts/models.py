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
