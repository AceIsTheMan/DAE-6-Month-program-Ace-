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

    # Cipher Token balance, shown in the nav notification dropdown's
    # Currency row and on the Store page (see mail.context_processors and
    # accounts/templates/home.html's token-square). Written by the
    # Director-only "!Token_<amount>" cheat code (accounts.views.
    # director_grant_tokens) and by accounts.views.store_purchase (a
    # Store token-pack buy).
    currency = models.IntegerField(default=0)

    # When this account's VIP access ends - None/in the past means no
    # active VIP. Written only by accounts.views.store_purchase: each VIP
    # purchase "stacks" by extending from the later of now/the current
    # expiry, rather than overwriting it, so buying more VIP time while
    # already a VIP never shortens what they already paid for.
    vip_expires_at = models.DateTimeField(null=True, blank=True)

    # Two of the six perks listed on the Store's VIP cards (see home.html)
    # made real - both gated to is_vip in settings_view's 'vip' sub-tab,
    # not just hidden in the template (same "server checks it too"
    # convention as every other gated tab here).
    SITE_THEME_CHOICES = [
        ('classic_red', 'Classic Red'),
        ('toxic_green', 'Toxic Green'),
        ('cyber_blue', 'Cyber Blue'),
        ('royal_purple', 'Royal Purple'),
        ('gold', 'Gold'),
    ]
    # Re-skins the site's --red/--red-bright/--red-dim CSS variables for
    # THIS account's own view only (see accounts/templates/
    # _vip_theme_override.html, included in both base.html and home.html
    # right after their own :root block) - a personal display
    # preference, not something other visitors see.
    site_theme = models.CharField(max_length=20, choices=SITE_THEME_CHOICES, default='classic_red')
    # Hex color (e.g. "#ff6600"), applied to how THIS account's username
    # is displayed to everyone, everywhere it appears (see
    # accounts/templates/_vip_name.html, used alongside _vip_badge.html
    # at every username call site). Blank = no override, falls back to
    # the site's normal text color.
    name_color = models.CharField(max_length=7, blank=True)

    # A third VIP perk, its own category below Custom Name Color in the
    # 'vip' settings sub-tab - a custom background image for VIP
    # Exclusive content (the Forum/Exclusive switch, see forum.models.
    # Post.is_vip_exclusive). Only 'none' exists for now; more themes
    # (kitty/soft-pink planned first) get appended here as their actual
    # background art is provided - adding one is just a new choices
    # entry plus whatever CSS/asset backs it, same pattern as
    # SITE_THEME_CHOICES above.
    BACKGROUND_THEME_CHOICES = [
        ('none', 'None (Default)'),
        ('kitty', 'Kitty Background'),
    ]
    background_theme = models.CharField(max_length=30, choices=BACKGROUND_THEME_CHOICES, default='none')

    @property
    def is_vip(self):
        return self.vip_expires_at is not None and self.vip_expires_at > timezone.now()

    @property
    def vip_days_remaining(self):
        if not self.is_vip:
            return 0
        return max(0, (self.vip_expires_at - timezone.now()).days)

    # Self-reported presence, set by the account owner in "// EDIT
    # PROFILE" (see accounts.forms.ProfileEditForm) and shown on their
    # profile dossier - NOT real presence detection (no login/heartbeat
    # tracking drives this) and NOT the same thing as Django's own
    # is_active (which actually blocks login) - this is purely a status
    # the user broadcasts about themselves, same spirit as a chat app's
    # manually-set "Online"/"Away" indicator.
    STATUS_ONLINE = 'online'
    STATUS_OFFLINE = 'offline'
    STATUS_ACTIVE = 'active'
    STATUS_DEACTIVATED = 'deactivated'
    STATUS_CHOICES = [
        (STATUS_ONLINE, 'Online'),
        (STATUS_OFFLINE, 'Offline'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DEACTIVATED, 'Deactivated'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ONLINE)

    # Settings tab, "Notifications" sub-tab - whether the unread-mail
    # badge (envelope nav icon + Mail sidebar counts, see mail.context_
    # processors.notification_counts) surfaces at all. Purely a display
    # toggle: messages still arrive and last_read_at still tracks
    # normally, this only decides whether that gets surfaced as a badge.
    notifications_enabled = models.BooleanField(default=True)

    # Settings tab, "Cutscenes" sub-tab - how often the Mail tab's
    # boot-up terminal splash (mail/templates/mail/index.html) plays.
    # COOLDOWN is the default so a first-time visitor sees it without
    # having to opt in, then it backs off on its own.
    CUTSCENE_ALWAYS = 'always'
    CUTSCENE_COOLDOWN = 'cooldown'
    CUTSCENE_NEVER = 'never'
    CUTSCENE_MODE_CHOICES = [
        (CUTSCENE_ALWAYS, 'Every time'),
        (CUTSCENE_COOLDOWN, '10 minute cooldown'),
        (CUTSCENE_NEVER, 'Never'),
    ]
    mail_cutscene_mode = models.CharField(max_length=10, choices=CUTSCENE_MODE_CHOICES, default=CUTSCENE_COOLDOWN)

    # Settings tab, "Cutscenes" sub-tab - on/off for "C1", the secret
    # breach cutscene (see accounts/templates/_secret_cutscene.html):
    # the 1-in-100 roll on switching back to the browser tab, and the
    # Director-only "!cmd_C1" cheat code. Off means neither ever plays
    # for this account, full stop - the cheat code doesn't override it,
    # so a Director who's turned this off doesn't get it either.
    secret_cutscene_enabled = models.BooleanField(default=True)

    # Drives which role-based terminal cutscene plays on login (see
    # accounts.signals.queue_role_cutscene_on_login and accounts/
    # templates/_role_cutscenes.html) - False only ever until this
    # account's very first successful login, at which point that signal
    # flips it True for good. Checking this (not Django's own
    # last_login) is deliberate: last_login is the SAME in-memory object
    # Django's own built-in update_last_login signal receiver also
    # mutates off the same user_logged_in signal, so whether it's still
    # None by the time our receiver runs depends on unguaranteed
    # receiver ordering. A dedicated field sidesteps that race entirely.
    has_completed_first_login = models.BooleanField(default=False)

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

    @property
    def is_moderator(self):
        """True for Admin or Director - the two roles allowed to view and
        act on the mail app's Reports queue (see mail.views.mail_reports).
        Everything else Director-only (forum posting/deleting, Directives)
        still checks is_director alone; this is the first feature in the
        project that actually uses the Admin role for something."""
        return self.role in (self.ROLE_ADMIN, self.ROLE_DIRECTOR)

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


class TokenGrantLog(models.Model):
    """
    Audit trail for the Director-only "!Token_<amount>" cheat code (typed
    into any text field anywhere on the site, same trigger shape as the
    "!cmd_*" cutscene previews in _role_cutscenes.html) - the only path
    that writes to CustomUser.currency right now. See
    accounts.views.director_grant_tokens.
    """
    director = models.ForeignKey(
        'CustomUser', on_delete=models.CASCADE, related_name='token_grants'
    )
    amount = models.PositiveIntegerField()
    new_balance = models.IntegerField(help_text='director.currency right after this grant.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.director.username} +{self.amount} -> {self.new_balance}'


class TokenTransaction(models.Model):
    """
    One line in a user's Cipher Token history - the ledger behind the
    Mail app's Cipher Tokens tab (mail.views.mail_tokens). Every change
    to CustomUser.currency should eventually create one of these; today
    the only writer is the Director's "!Token_<amount>" cheat code
    (accounts.views.director_grant_tokens, kind=ADMIN_GRANT) since
    nothing else (VIP, the Store token packs) is wired to a real
    purchase/gift/win flow yet - see that view's docstring.

    `amount` is signed: positive for anything that adds tokens (gift/
    purchase/won/admin_grant), negative for SPENT. `balance_after` snapshots
    currency right after this row was applied, so the history view can
    just order by created_at and read each row's own balance_after
    instead of replaying the whole ledger to reconstruct a running total.
    """
    GIFT = 'gift'
    PURCHASE = 'purchase'
    WON = 'won'
    ADMIN_GRANT = 'admin_grant'
    SPENT = 'spent'
    KIND_CHOICES = [
        (GIFT, 'Gift'),
        (PURCHASE, 'Purchase'),
        (WON, 'Won'),
        (ADMIN_GRANT, 'Admin Grant'),
        (SPENT, 'Spent'),
    ]
    #: Kinds that add to the balance - everything else (just SPENT today)
    #: subtracts. Used to split "earned" vs. "spent" in the history tab.
    EARNED_KINDS = (GIFT, PURCHASE, WON, ADMIN_GRANT)

    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='token_transactions')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.IntegerField(help_text='Signed - positive for earned, negative for spent.')
    balance_after = models.IntegerField()
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f'{self.user.username} {sign}{self.amount} ({self.get_kind_display()})'


class PurchaseLog(models.Model):
    """
    One real (fake-money) Store transaction - VIP purchases, token pack
    purchases, and "buy new tokens to gift" sends each log one row here,
    credited to the PAYING account regardless of who the tokens/VIP
    ultimately went to. Backs the "Top Donators" leaderboard on the
    Socials & Support page (home.html's page-socials section, see
    accounts.views.home_view) - ranked by a Sum of amount_cents.

    Deliberately separate from TokenTransaction: that's a per-user
    currency ledger (what changed someone's balance and why). This is
    purely "how much fake money did this account spend in the Store" -
    VIP purchases never touch currency at all, and "gift from my own
    balance" (TokenTransaction.SPENT) is moving tokens that were already
    paid for once, not new spending, so neither should (and neither
    does) create a row here. See accounts.views.store_purchase/
    store_gift - every write path to this model.
    """
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='purchase_logs')
    item_key = models.CharField(max_length=20)
    label = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    amount_cents = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - ${self.amount_cents / 100:.2f} ({self.label})'
