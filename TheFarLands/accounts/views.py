import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from forum.models import Comment, Post
from mail.forms import _is_blocked_pair
from mail.models import FriendRequest, Message, ModerationAction, Report, RoleChangeLog, UserRelationship, Warning
from mail.views import _get_or_create_dm

from .forms import GuestRegisterForm, ProfileEditForm, RegisterForm
from .models import BannerLoadout, CustomUser, GuestArchive, PurchaseLog, TokenGrantLog, TokenTransaction

# Store catalog - the one source of truth for what each Store button
# actually buys, keyed to match each button's `data-item` in home.html's
# Store page. Prices/amounts are trusted from here, never from the
# client, so a tampered POST can't buy more than what's listed - see
# store_purchase below. "cents" throughout (not dollars) to avoid float
# rounding on money math.
STORE_CATALOG = {
    'vip_month': {'label': 'VIP Membership', 'kind': 'vip', 'unit_price_cents': 500, 'unit_days': 30},
    'vip_year': {'label': 'VIP Membership (Annual)', 'kind': 'vip', 'unit_price_cents': 2000, 'unit_days': 365},
    'tokens_4': {'label': '4 Tokens', 'kind': 'tokens', 'unit_price_cents': 100, 'unit_tokens': 4},
    'tokens_40': {'label': '40 Tokens', 'kind': 'tokens', 'unit_price_cents': 1000, 'unit_tokens': 40},
    'tokens_400': {'label': '400 Tokens', 'kind': 'tokens', 'unit_price_cents': 10000, 'unit_tokens': 400},
}
#: "how many times the account can purchase in 1 go" - a quantity
#: multiplier on one checkout, capped so a typo doesn't buy 9999 VIP
#: months in one click.
STORE_MAX_QUANTITY = 50

# kind (used in the Chat Logs URLs/template) -> (model, author/sender field name)
CHAT_LOG_MODELS = {
    'post': (Post, 'author'),
    'comment': (Comment, 'author'),
    'message': (Message, 'sender'),
}

# Chat Logs search (settings_view's 'logs' tab) - a wide-open search across
# the whole site's history could return an unbounded number of rows, so
# results are capped and the template is told the real total separately
# (see _chat_log_matches) rather than silently truncating with no signal.
CHAT_LOG_SEARCH_LIMIT = 200


def _parse_local_datetime(raw):
    """Parse a `<input type="datetime-local">` value ("YYYY-MM-DDTHH:MM")
    into an aware datetime in the project's TIME_ZONE - the Chat Logs
    date/time filters compare this against `created_at`, which Django
    always stores/queries in UTC once USE_TZ is on (see tfl_site/
    settings.py). Returns None for a blank or unparseable value instead
    of raising, so a malformed query string just drops that one filter
    rather than 500ing the whole search."""
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _chat_log_matches(deleted_only, q='', log_user='', date_from=None, date_to=None):
    """Every Post/Comment/Message matching the Chat Logs tab's filters -
    just the soft-deleted queue (deleted_only=True, the tab's default
    view, unchanged from before search existed) or, once a Director
    actually searches, every message regardless of is_deleted (so
    "who said what, and when" can be answered for live conversations
    too, not just ones that got deleted). Newest first, capped at
    CHAT_LOG_SEARCH_LIMIT. Returns (entries, total_count) - total_count
    is the real match count before the cap, so the template can say
    "showing 200 of 1,240 matches" instead of quietly cutting results."""
    entries = []
    total_count = 0
    for kind, (model, author_field) in CHAT_LOG_MODELS.items():
        qs = model.objects.select_related(author_field, 'deleted_by')
        if deleted_only:
            qs = qs.filter(is_deleted=True)
        if q:
            qs = qs.filter(body__icontains=q)
        if log_user:
            qs = qs.filter(**{f'{author_field}__username__icontains': log_user})
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)
        total_count += qs.count()
        for obj in qs.order_by('-created_at')[:CHAT_LOG_SEARCH_LIMIT]:
            entries.append({
                'kind': kind,
                'id': obj.pk,
                'author': getattr(obj, author_field),
                'body': obj.body,
                'created_at': obj.created_at,
                'is_deleted': obj.is_deleted,
                'deleted_at': obj.deleted_at,
                'deleted_by': obj.deleted_by,
            })
    entries.sort(key=lambda e: e['created_at'], reverse=True)
    return entries[:CHAT_LOG_SEARCH_LIMIT], total_count


def _annotate_moderation_counts(queryset):
    """Attach warning_count/mute_count/ban_count/perm_ban_count to a
    CustomUser queryset - shared by the Dashboard's user search and the
    Director-only All Users tab, both of which need "how many
    warns/bans has this account gotten" at a glance."""
    return queryset.annotate(
        warning_count=Count('warnings_received', distinct=True),
        mute_count=Count(
            'moderation_actions_received',
            filter=Q(moderation_actions_received__kind=ModerationAction.MUTE), distinct=True,
        ),
        ban_count=Count(
            'moderation_actions_received',
            filter=Q(moderation_actions_received__kind=ModerationAction.BAN), distinct=True,
        ),
        perm_ban_count=Count(
            'moderation_actions_received',
            filter=Q(moderation_actions_received__kind=ModerationAction.PERM_BAN), distinct=True,
        ),
    )


def _report_target(report):
    if report.reported_user_id:
        return report.reported_user
    if report.reported_message_id:
        return report.reported_message.sender
    if report.reported_comment_id:
        return report.reported_comment.author
    return None


def _admin_activity_entries():
    """Everything an Admin-role account has done that a Director should
    be able to audit - see the "Admin Logs" panel referenced throughout
    mail.models (Warning, RoleChangeLog) and mail.views (report resolve/
    warn). Admins have deliberately reduced authority (can't moderate
    other admins, report resolves are only a request) - this is how a
    Director keeps an eye on what they're doing with the authority they
    do have."""
    entries = []

    for action in ModerationAction.objects.filter(
        moderator__role=CustomUser.ROLE_ADMIN
    ).select_related('moderator', 'target'):
        entries.append({
            'type_label': action.get_kind_display(),
            'actor': action.moderator,
            'target': action.target,
            'detail': action.reason,
            'created_at': action.created_at,
        })

    for warning in Warning.objects.filter(
        issued_by__role=CustomUser.ROLE_ADMIN
    ).select_related('issued_by', 'target'):
        entries.append({
            'type_label': f'Warning ({warning.get_source_display()})',
            'actor': warning.issued_by,
            'target': warning.target,
            'detail': warning.message,
            'created_at': warning.created_at,
        })

    for report in Report.objects.filter(
        admin_requested_by__role=CustomUser.ROLE_ADMIN
    ).select_related('admin_requested_by', 'reported_user', 'reported_message__sender', 'reported_comment__author'):
        entries.append({
            'type_label': f'Requested {report.get_admin_requested_status_display()}',
            'actor': report.admin_requested_by,
            'target': _report_target(report),
            'detail': f'Report #{report.pk}: {report.reason}',
            'created_at': report.admin_requested_at,
        })

    for change in RoleChangeLog.objects.filter(
        Q(old_role=CustomUser.ROLE_ADMIN) | Q(new_role=CustomUser.ROLE_ADMIN)
    ).select_related('changed_by', 'target'):
        entries.append({
            'type_label': f'Role changed ({change.old_role} → {change.new_role})',
            'actor': change.changed_by,
            'target': change.target,
            'detail': '',
            'created_at': change.created_at,
        })

    entries.sort(key=lambda e: e['created_at'], reverse=True)
    return entries


def home_view(request):
    """
    Public landing page - The Far Lands main site (the old TFL_index.html,
    now served through Django so login state is real instead of guessed).

    force_rules_gate is a one-shot flag set by accounts.signals whenever
    someone just logged in (regular or guest) - it tells the template/JS to
    show the "BE ADVISED" rules popup again even if this browser tab
    already dismissed it earlier as an anonymous visitor. It's popped (read
    AND removed) here so it only fires on the page load right after login,
    not on every later visit to home in the same session.

    role_cutscene is the same one-shot shape, from the same login event
    (see accounts.signals.queue_role_cutscene_on_login) - which role-based
    terminal cutscene (see accounts/templates/_role_cutscenes.html) to
    auto-play once the rules gate above is dismissed.

    guest_trial_remaining is only ever computed for a signed-in guest -
    the real "days:hours:minutes" left on their trial (see CustomUser.
    guest_expires_at), fed into the guest_login cutscene's countdown
    line rather than a hardcoded number, unlike guest_create's.

    director_profile_picture_url is only computed when an Admin's own
    login just queued admin_login - the real Director's picture (there's
    only ever one), for the simulated "Director pfp" chat message that
    cutscene shows.

    top_donators backs the leaderboard below the donation box on the
    Socials & Support tab - the 10 accounts with the highest total real
    (fake-money) Store spending (accounts.models.PurchaseLog), VIP and
    token purchases/gifts alike. Computed unconditionally (cheap - one
    aggregate query, capped at 10 rows) since every page tab's markup
    renders on every load here, the JS just toggles which one shows.

    top_banner_url/bottom_banner_url are the currently-active
    BannerLoadout's images (Settings > Banners, Director-only, see
    settings_view) - a true site-wide setting, not a per-account
    preference like VIP Background Themes. Falls back to the original
    static banner files if the active loadout leaves either blank.
    """
    force_rules_gate = request.session.pop('force_rules_gate', False)
    role_cutscene = request.session.pop('role_cutscene', '')

    guest_trial_remaining = ''
    if request.user.is_authenticated and request.user.is_guest:
        remaining_seconds = max(0, (request.user.guest_expires_at - timezone.now()).total_seconds())
        total_minutes = int(remaining_seconds // 60)
        days, rem_minutes = divmod(total_minutes, 24 * 60)
        hours, minutes = divmod(rem_minutes, 60)
        guest_trial_remaining = f'{days}:{hours:02d}:{minutes:02d}'

    director_profile_picture_url = ''
    if role_cutscene == 'admin_login':
        director = CustomUser.objects.filter(role=CustomUser.ROLE_DIRECTOR).first()
        if director and director.profile_picture:
            director_profile_picture_url = director.profile_picture.url

    top_donators = [
        {'user': u, 'total_donated': u.total_donated_cents / 100}
        for u in CustomUser.objects.filter(purchase_logs__isnull=False)
        .annotate(total_donated_cents=Sum('purchase_logs__amount_cents'))
        .order_by('-total_donated_cents')[:10]
    ]

    # Site-wide Home page banners (Settings > Banners, Director-only -
    # see settings_view). Whichever BannerLoadout is_active=True wins; a
    # blank top/bottom banner on it (including "Regular", which ships
    # with both left blank on purpose) falls back to the site's
    # original static banner images rather than a broken <img>.
    active_loadout = BannerLoadout.objects.filter(is_active=True).first()
    top_banner_url = (
        active_loadout.top_banner.url if active_loadout and active_loadout.top_banner
        else static('accounts/Banner 2.jpg')
    )
    bottom_banner_url = (
        active_loadout.bottom_banner.url if active_loadout and active_loadout.bottom_banner
        else static('accounts/Banners.jpg')
    )

    return render(request, 'home.html', {
        'force_rules_gate': force_rules_gate,
        'role_cutscene_to_play': role_cutscene,
        'director_profile_picture_url': director_profile_picture_url,
        'guest_trial_remaining': guest_trial_remaining,
        'top_donators': top_donators,
        'top_banner_url': top_banner_url,
        'bottom_banner_url': bottom_banner_url,
    })


def _send_verification_email(request, user):
    """
    Emails a one-time verification link to a newly-registered (non-guest)
    account. Uses Django's own password-reset token machinery
    (default_token_generator) purely because it already does exactly what
    we need here too: a signed, single-use-ish token tied to this specific
    user that can't be guessed or reused once the account state it was
    built from (password / last_login) changes.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(
        reverse('verify_email', args=[uidb64, token])
    )
    send_mail(
        subject='Verify your Far Lands account',
        message=(
            f'Hey {user.username},\n\n'
            f'Click the link below to verify your email and activate your '
            f'Far Lands account:\n\n{verify_url}\n\n'
            f"If you didn't sign up for this, you can just ignore this email."
        ),
        from_email=None,  # falls back to settings.DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
    )


def register_view(request):
    """
    Handle new agent registration.
    GET  -> show the blank form.
    POST -> validate it; on success, create the account (email_verified=False
            until they click the link - see RegisterForm.save()), email them
            a verification link, and show a "check your email" page. They
            aren't logged in yet - that happens after they click the link
            and then log in normally. On failure, re-render the form with
            field-by-field error messages.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Verification feature is toggled off for now (see
            # settings.EMAIL_VERIFICATION_ENABLED) - RegisterForm.save()
            # already auto-verified the account, so there's no link to
            # send; skip straight to "you're set, go log in" instead of
            # "check your email".
            if settings.EMAIL_VERIFICATION_ENABLED:
                _send_verification_email(request, user)
            return render(request, 'registration/check_email.html', {
                'email': user.email,
                'is_console_backend': settings.EMAIL_BACKEND.endswith('console.EmailBackend'),
                'verification_enabled': settings.EMAIL_VERIFICATION_ENABLED,
            })
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


def verify_email_view(request, uidb64, token):
    """
    Handles the link from _send_verification_email(). Marks the account
    email_verified=True (NOT is_active - see CustomUser.email_verified's
    docstring for why those had to be separate flags) if the uid decodes to
    a real user and the token checks out; otherwise shows a "link
    invalid/expired" message instead of erroring. Doesn't log the user in
    itself - they still go through /login/ normally afterward, same as
    everyone else.
    """
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    verified = False
    if user is not None and default_token_generator.check_token(user, token):
        user.email_verified = True
        user.save()
        verified = True

    return render(request, 'registration/verify_result.html', {'verified': verified})


def guest_register_view(request):
    """
    Handle temporary "Hacker" guest registration - just a codename and
    password, no email. Same flow as a normal registration otherwise (log
    in immediately, land on home): the account is simply marked
    is_guest=True, which is what limits it everywhere else - no profile
    picture, shown as HACKER instead of AGENT on their profile, and
    automatically deleted after CustomUser.GUEST_TRIAL_DAYS by
    GuestExpiryMiddleware.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = GuestRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_guest = True
            user.role = CustomUser.ROLE_HACKER
            user.save()
            login(request, user)
            return redirect('home')
    else:
        form = GuestRegisterForm()

    return render(request, 'registration/guest_register.html', {'form': form})


@login_required
def profile_view(request, username=None):
    """
    Display a user's profile. Defaults to the logged-in user's profile.

    When you're looking at your OWN profile, this also handles saving
    edits (bio / profile picture) right on the same page - no separate
    "stuck on an edit screen" step.
    """
    if username:
        user = get_object_or_404(CustomUser, username=username)
    else:
        user = request.user

    is_own_profile = (user == request.user)
    edit_form = None

    if is_own_profile:
        if request.method == 'POST':
            edit_form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
            if edit_form.is_valid():
                edit_form.save()
                return redirect('profile')
        else:
            edit_form = ProfileEditForm(instance=request.user)

    # Message/Friend/Block are only offered between two real, non-guest
    # accounts (see mail.views._require_mail_access) - computed here so
    # profile.html's template logic stays simple booleans, not a chain of
    # `and`/`not` that {% include ... with %} can't express anyway.
    can_use_mail_with_them = (
        not is_own_profile
        and request.user.is_authenticated
        and not request.user.is_guest
        and not user.is_guest
    )

    # "Moderation" in the 3-dot menu (see _dots_menu.html) - real Mute/
    # Ban/Perm Ban power (mail.models.ModerationAction), not the
    # self-service Friend/Mute/Block above. Director is never a valid
    # target, mirroring mail.views.mail_moderation_new's own check.
    can_moderate_them = (
        not is_own_profile
        and request.user.is_authenticated
        and request.user.is_moderator
        and not user.is_director
    )

    # An active Mute/Ban/Perm Ban (mail.models.ModerationAction) takes
    # over the Status row on the dossier entirely - see
    # ModerationAction.status_label and templates/profile.html.
    active_moderation = ModerationAction.active_for(
        user, [ModerationAction.MUTE, ModerationAction.BAN, ModerationAction.PERM_BAN]
    )

    # See FriendRequest.state_between - drives which of Friend/Pending/
    # Unfriend/Accept+Decline the dots-menu shows for this pair.
    friend_state = FriendRequest.state_between(request.user, user) if can_use_mail_with_them else 'none'
    pending_request_from_them = None
    if friend_state == 'pending_received':
        pending_request_from_them = FriendRequest.objects.filter(
            from_user=user, to_user=request.user, status=FriendRequest.PENDING
        ).first()

    # Fan Letter only ever targets the Director, and only from someone
    # else's non-guest account - see mail.views.mail_fan_letter_new.
    show_fan_letter = not is_own_profile and not request.user.is_guest and user.is_director

    return render(request, 'profile.html', {
        'profile_user': user,
        'edit_form': edit_form,
        'can_use_mail_with_them': can_use_mail_with_them,
        'can_moderate_them': can_moderate_them,
        'active_moderation': active_moderation,
        'friend_state': friend_state,
        'pending_request_from_them': pending_request_from_them,
        'show_fan_letter': show_fan_letter,
    })


@login_required
def toggle_status(request):
    """
    Quick one-click Online/Offline toggle for the Status row on your OWN
    profile (see profile.html) - entirely optional, changes nothing if
    never clicked. Deliberately narrower than the full "// EDIT PROFILE"
    Status dropdown (accounts.forms.ProfileEditForm), which still covers
    all four states including Active/Deactivated: this button only ever
    lands on Online or Offline - anything else (Active/Deactivated)
    counts as "not Offline" and flips to Offline on the first click.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    user = request.user
    user.status = CustomUser.STATUS_ONLINE if user.status == CustomUser.STATUS_OFFLINE else CustomUser.STATUS_OFFLINE
    user.save(update_fields=['status'])
    return JsonResponse({'status': user.status, 'status_display': user.get_status_display()})


@login_required
def settings_view(request):
    """
    Gear/settings nav icon (see _nav_mail_icons.html) - tabs: Settings
    (every account's own personal settings - Profile/Blocked/
    Notifications/Cutscenes sub-tabs, see below), Dashboard (Admin/
    Director-only entry point into moderator tools, including a
    by-username account search with warn/mute/ban counts and the
    expired-guest archive - see accounts.models.GuestArchive), and four
    Director-only tabs: Chat Logs (the soft-deleted Post/Comment/Message
    queue, Re-Send/Purge, by default - or, once a keyword/username/date
    filter is used, a search across ALL Post/Comment/Message content,
    deleted or not - see _chat_log_matches), Admin Logs (an audit trail
    of what Admin-role accounts have done - see
    _admin_activity_entries), All Users (every account on the site
    with its full account info), and Banners (accounts.models.
    BannerLoadout - manages the Home page's top/bottom banner images
    site-wide for every visitor, not a per-account preference like VIP
    Background Themes; whichever loadout is_active=True wins, see
    home_view). Every gated tab is checked server-side, not just hidden
    by the tab UI - same convention as every other moderator-only view
    (see accounts.models.CustomUser.is_moderator/is_director).

    The Settings tab itself has its own row of sub-tabs (`sub` query
    param, defaults to 'profile'):
      - profile: the same "// EDIT PROFILE" form/crop-tool as /profile/,
        via the shared _profile_edit_panel.html include - a second entry
        point to the same account fields, not a second form.
      - blocked: every account this user has blocked (mail.models.
        UserRelationship, kind=BLOCK) with an Unblock action - reuses
        mail.views.mail_relationship_block's existing toggle endpoint via
        fetch rather than a new one.
      - notifications: on/off for the unread-mail badge (see mail.
        context_processors.notification_counts) - CustomUser.
        notifications_enabled.
      - cutscenes: Always/10-Minute Cooldown/Never for the Mail tab's
        boot-up terminal splash (CustomUser.mail_cutscene_mode, read by
        mail/templates/mail/index.html's own script), plus a separate
        on/off for "C1", the secret breach cutscene (CustomUser.
        secret_cutscene_enabled - see accounts/templates/
        _secret_cutscene.html and settings_toggle_secret_cutscene).
      - vip: VIP-only (gated server-side, not just hidden in the tab
        strip) - site theme (CustomUser.site_theme, re-skins this
        account's own view of the site, see _vip_theme_override.html),
        a custom name color (CustomUser.name_color, changes how this
        account's username displays to everyone, see _vip_name.html),
        and Background Themes (CustomUser.background_theme, a custom
        background for VIP Exclusive content - only 'none' exists for
        now, more get added as their art is provided). Perks listed on
        the Store's VIP cards, made real.
    """
    active_tab = request.GET.get('tab', 'settings')
    if active_tab == 'dashboard' and not request.user.is_moderator:
        active_tab = 'settings'
    if active_tab in ('logs', 'admin_logs', 'users', 'banners') and not request.user.is_director:
        active_tab = 'settings'

    context = {'active_tab': active_tab}
    if active_tab == 'settings':
        active_sub_tab = request.GET.get('sub', 'profile')
        valid_sub_tabs = ['profile', 'blocked', 'notifications', 'cutscenes']
        if request.user.is_vip:
            valid_sub_tabs.append('vip')
        if active_sub_tab not in valid_sub_tabs:
            active_sub_tab = 'profile'
        context['active_sub_tab'] = active_sub_tab
        context['cutscene_mode_choices'] = CustomUser.CUTSCENE_MODE_CHOICES

        if active_sub_tab == 'profile':
            if request.method == 'POST':
                edit_form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
                if edit_form.is_valid():
                    edit_form.save()
                    return redirect(f"{reverse('settings_page')}?tab=settings&sub=profile")
            else:
                edit_form = ProfileEditForm(instance=request.user)
            context['edit_form'] = edit_form
        elif active_sub_tab == 'blocked':
            context['blocked_users'] = (
                UserRelationship.objects.filter(from_user=request.user, kind=UserRelationship.BLOCK)
                .select_related('to_user')
                .order_by('to_user__username')
            )
        elif active_sub_tab == 'vip':
            if request.method == 'POST':
                update_fields = []
                # Checked with `in request.POST`, not a blanket .get(...,
                # ''), since the theme-only form and the name-color-only
                # form each omit the other field entirely - a plain
                # .get() default would silently wipe out whichever one
                # wasn't actually submitted this time.
                if 'site_theme' in request.POST:
                    site_theme = request.POST.get('site_theme', '')
                    if site_theme in dict(CustomUser.SITE_THEME_CHOICES):
                        request.user.site_theme = site_theme
                        update_fields.append('site_theme')
                if 'name_color' in request.POST:
                    name_color = request.POST.get('name_color', '').strip()
                    # Blank clears it back to the default text color;
                    # anything else must be a real #rrggbb or it's
                    # silently dropped rather than saving a value CSS
                    # can't use.
                    if name_color == '' or re.fullmatch(r'#[0-9a-fA-F]{6}', name_color):
                        request.user.name_color = name_color
                        update_fields.append('name_color')
                if 'background_theme' in request.POST:
                    background_theme = request.POST.get('background_theme', '')
                    if background_theme in dict(CustomUser.BACKGROUND_THEME_CHOICES):
                        request.user.background_theme = background_theme
                        update_fields.append('background_theme')
                if update_fields:
                    request.user.save(update_fields=update_fields)
                return redirect(f"{reverse('settings_page')}?tab=settings&sub=vip")
            context['site_theme_choices'] = CustomUser.SITE_THEME_CHOICES
            context['background_theme_choices'] = CustomUser.BACKGROUND_THEME_CHOICES
    elif active_tab == 'dashboard':
        context.update({
            'total_accounts': CustomUser.objects.count(),
            'guest_accounts': CustomUser.objects.filter(is_guest=True).count(),
            'open_reports': Report.objects.filter(status=Report.OPEN).count(),
            'expired_guests': GuestArchive.objects.all(),
        })
        query = request.GET.get('q', '').strip()
        if query:
            context['user_search_results'] = _annotate_moderation_counts(
                CustomUser.objects.filter(username__icontains=query)
            ).order_by('username')[:25]
        context['user_search_query'] = query
    elif active_tab == 'users':
        context['all_users'] = _annotate_moderation_counts(CustomUser.objects.all()).order_by('-date_joined')
    elif active_tab == 'logs':
        query = request.GET.get('q', '').strip()
        log_user = request.GET.get('log_user', '').strip()
        raw_date_from = request.GET.get('date_from', '')
        raw_date_to = request.GET.get('date_to', '')
        date_from = _parse_local_datetime(raw_date_from)
        date_to = _parse_local_datetime(raw_date_to)
        searching = bool(query or log_user or date_from or date_to)
        context.update({
            'log_search_query': query,
            'log_search_user': log_user,
            'log_search_date_from': raw_date_from,
            'log_search_date_to': raw_date_to,
            'log_searching': searching,
        })
        if searching:
            entries, total_count = _chat_log_matches(
                deleted_only=False, q=query, log_user=log_user, date_from=date_from, date_to=date_to,
            )
            context['log_search_total'] = total_count
        else:
            entries, _total = _chat_log_matches(deleted_only=True)
        context['log_entries'] = entries
    elif active_tab == 'admin_logs':
        context['admin_log_entries'] = _admin_activity_entries()
    elif active_tab == 'banners':
        if request.method == 'POST':
            action = request.POST.get('action', '')
            loadout_id = request.POST.get('loadout_id', '')
            loadout = BannerLoadout.objects.filter(pk=loadout_id).first() if loadout_id else None

            if action == 'activate' and loadout:
                BannerLoadout.objects.exclude(pk=loadout.pk).update(is_active=False)
                loadout.is_active = True
                loadout.save(update_fields=['is_active'])
            elif action == 'upload' and loadout:
                update_fields = []
                if request.FILES.get('top_banner'):
                    loadout.top_banner = request.FILES['top_banner']
                    update_fields.append('top_banner')
                if request.FILES.get('bottom_banner'):
                    loadout.bottom_banner = request.FILES['bottom_banner']
                    update_fields.append('bottom_banner')
                if update_fields:
                    loadout.updated_by = request.user
                    loadout.save(update_fields=update_fields + ['updated_by', 'updated_at'])
            elif action == 'reset_top' and loadout:
                loadout.top_banner = None
                loadout.updated_by = request.user
                loadout.save(update_fields=['top_banner', 'updated_by', 'updated_at'])
            elif action == 'reset_bottom' and loadout:
                loadout.bottom_banner = None
                loadout.updated_by = request.user
                loadout.save(update_fields=['bottom_banner', 'updated_by', 'updated_at'])
            elif action == 'create':
                name = request.POST.get('name', '').strip()[:50]
                if name:
                    BannerLoadout.objects.create(name=name, updated_by=request.user)
            elif action == 'delete' and loadout and not loadout.is_active:
                loadout.delete()
            return redirect(f"{reverse('settings_page')}?tab=banners")
        context['banner_loadouts'] = BannerLoadout.objects.all()
    return render(request, 'settings.html', context)


@login_required
def settings_toggle_notifications(request):
    """Settings tab, Notifications sub-tab - flips CustomUser.
    notifications_enabled, same plain on/off toggle shape as toggle_status
    above. See mail.context_processors.notification_counts for what this
    actually suppresses (the unread badge only, never message delivery
    or last_read_at tracking)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    request.user.notifications_enabled = not request.user.notifications_enabled
    request.user.save(update_fields=['notifications_enabled'])
    return redirect(f"{reverse('settings_page')}?tab=settings&sub=notifications")


@login_required
def settings_update_cutscene_mode(request):
    """Settings tab, Cutscenes sub-tab - sets CustomUser.
    mail_cutscene_mode from the posted radio choice. An unrecognized
    value is just ignored (stays whatever it was) rather than erroring,
    same defensive shape as mail.views.mail_report_resolve's status
    param."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    mode = request.POST.get('mode', '')
    if mode in dict(CustomUser.CUTSCENE_MODE_CHOICES):
        request.user.mail_cutscene_mode = mode
        request.user.save(update_fields=['mail_cutscene_mode'])
    return redirect(f"{reverse('settings_page')}?tab=settings&sub=cutscenes")


@login_required
def settings_toggle_secret_cutscene(request):
    """Settings tab, Cutscenes sub-tab - flips CustomUser.
    secret_cutscene_enabled, the on/off switch for "C1" (see accounts/
    templates/_secret_cutscene.html). Off suppresses both ways it can
    play - the random 1/100 roll and the Director-only "!cmd_C1" cheat
    code - there's no override."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    request.user.secret_cutscene_enabled = not request.user.secret_cutscene_enabled
    request.user.save(update_fields=['secret_cutscene_enabled'])
    return redirect(f"{reverse('settings_page')}?tab=settings&sub=cutscenes")


@login_required
def chat_log_resend(request, kind, obj_id):
    """Un-delete a soft-deleted Post/Comment/Message from the Director-only
    Chat Logs panel - flips is_deleted back to False, nothing else ever
    moved (see the soft-delete docstrings on each model)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can manage Chat Logs.')
    entry = CHAT_LOG_MODELS.get(kind)
    if entry is None:
        raise Http404
    model, _ = entry
    obj = get_object_or_404(model, pk=obj_id, is_deleted=True)
    obj.is_deleted = False
    obj.deleted_at = None
    obj.deleted_by = None
    obj.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    return redirect(f"{reverse('settings_page')}?tab=logs")


@login_required
def chat_log_purge(request, kind, obj_id):
    """Permanently delete a soft-deleted Post/Comment/Message - a real
    .delete(), the only way anything ever truly leaves the Chat Logs
    panel."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can manage Chat Logs.')
    entry = CHAT_LOG_MODELS.get(kind)
    if entry is None:
        raise Http404
    model, _ = entry
    obj = get_object_or_404(model, pk=obj_id, is_deleted=True)
    obj.delete()
    return redirect(f"{reverse('settings_page')}?tab=logs")


# Sanity ceiling for the "!Token_<amount>" cheat code below - not a real
# economic limit (the Director can just run it again), just a guard
# against a fat-fingered extra zero or two silently wrecking the balance.
MAX_CHEAT_TOKEN_GRANT = 1_000_000


@login_required
def director_grant_tokens(request):
    """Backing endpoint for the Director-only "!Token_<amount>" cheat
    code - same trigger shape as the "!cmd_*" cutscene previews
    (typed into any text field anywhere on the site, see
    _role_cutscenes.html's global `input` listener), except this one
    actually writes to the database instead of just playing an
    animation: it adds <amount> Cipher Tokens to the Director's own
    CustomUser.currency, records a TokenGrantLog row (Director-specific
    admin audit trail), and a TokenTransaction row (the user-facing
    ledger entry shown on the Mail app's Cipher Tokens tab)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can use the token cheat code.')

    try:
        amount = int(request.POST.get('amount', ''))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid amount.'}, status=400)
    if amount <= 0 or amount > MAX_CHEAT_TOKEN_GRANT:
        return JsonResponse({'error': f'Amount must be between 1 and {MAX_CHEAT_TOKEN_GRANT}.'}, status=400)

    request.user.currency += amount
    request.user.save(update_fields=['currency'])
    TokenGrantLog.objects.create(director=request.user, amount=amount, new_balance=request.user.currency)
    TokenTransaction.objects.create(
        user=request.user,
        kind=TokenTransaction.ADMIN_GRANT,
        amount=amount,
        balance_after=request.user.currency,
        note='Director cheat code (!Token_<amount>)',
    )
    return JsonResponse({'amount': amount, 'balance': request.user.currency})


@login_required
def store_purchase(request):
    """Backing endpoint for the Store page's purchase popup (see
    home.html's `.store-checkout-modal` and its JS). Still fake money -
    `payment_method` is accepted and echoed back for the receipt but
    never validated/charged against anything, same spirit as the rest of
    this Store (VIP/token prices are cosmetic, there's no real payment
    gateway). What IS real: `item`/`quantity` are priced from
    STORE_CATALOG (never trusted from the client) and the resulting
    tokens/VIP time are actually applied to the account.

    VIP "stacks": a purchase extends from the later of now or the
    account's current vip_expires_at, so buying more time while already
    VIP adds to what's left instead of overwriting it."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if request.user.is_guest:
        return JsonResponse({'error': 'Guest accounts cannot use the Store.'}, status=403)

    item_key = request.POST.get('item', '')
    item = STORE_CATALOG.get(item_key)
    if item is None:
        return JsonResponse({'error': 'Unknown item.'}, status=400)

    try:
        quantity = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid quantity.'}, status=400)
    if quantity < 1 or quantity > STORE_MAX_QUANTITY:
        return JsonResponse({'error': f'Quantity must be between 1 and {STORE_MAX_QUANTITY}.'}, status=400)

    payment_method = request.POST.get('payment_method', 'card')
    if payment_method not in ('card', 'paypal', 'cipher_pay'):
        payment_method = 'card'

    total_price_cents = item['unit_price_cents'] * quantity
    response = {
        'item': item_key,
        'label': item['label'],
        'kind': item['kind'],
        'quantity': quantity,
        'payment_method': payment_method,
        'total_price_cents': total_price_cents,
    }

    # Every STORE_CATALOG item has a real price, so every store_purchase
    # call is real (fake-money) spending - counts toward the Top
    # Donators leaderboard regardless of whether it bought tokens or VIP.
    PurchaseLog.objects.create(
        user=request.user, item_key=item_key, label=item['label'], quantity=quantity, amount_cents=total_price_cents,
    )

    if item['kind'] == 'tokens':
        total_tokens = item['unit_tokens'] * quantity
        request.user.currency += total_tokens
        request.user.save(update_fields=['currency'])
        TokenTransaction.objects.create(
            user=request.user,
            kind=TokenTransaction.PURCHASE,
            amount=total_tokens,
            balance_after=request.user.currency,
            note=f'{quantity}x {item["label"]} ({payment_method})',
        )
        response['total_tokens'] = total_tokens
        response['balance'] = request.user.currency
    else:  # 'vip'
        total_days = item['unit_days'] * quantity
        base = request.user.vip_expires_at if request.user.is_vip else timezone.now()
        request.user.vip_expires_at = base + timedelta(days=total_days)
        request.user.save(update_fields=['vip_expires_at'])
        response['total_days'] = total_days
        response['vip_expires_at'] = request.user.vip_expires_at.isoformat()
        response['vip_days_remaining'] = request.user.vip_days_remaining

    return JsonResponse(response)


#: "they can gift as many times in 1 gift as they want" - still bounded
#: so a mis-typed quantity can't overflow an IntegerField; 'own'-balance
#: gifts are additionally bounded by the sender's real balance below.
GIFT_MAX_QUANTITY = 1_000_000


@login_required
def store_gift(request):
    """Backing endpoint for the Store's Gift card (see home.html's gift
    fields on the shared checkout modal). Same STORE_CATALOG pricing as
    store_purchase, except the tokens/VIP land on a chosen recipient
    instead of the buyer, and the recipient gets a Mail DM announcing it
    (reusing mail.views._get_or_create_dm - the same find-or-create DM
    thread every other cross-account notice in Mail uses).

    Token gifts take a `source`:
      - 'buy' (default): fresh tokens, paid for (fake) by the sender -
        the recipient's balance goes up, the sender's doesn't move.
      - 'own': transferred out of the sender's own existing balance -
        they must actually have that many tokens. Logs a SPENT row for
        the sender (so it shows in their monthly spent summary on the
        Cipher Tokens tab) alongside the recipient's GIFT row.
    VIP gifts have no 'own' mode - VIP isn't a transferable balance, so
    it's always bought fresh for the recipient, stacking onto whatever
    VIP time they already have left (same stacking rule as
    store_purchase)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if request.user.is_guest:
        return JsonResponse({'error': 'Guest accounts cannot use the Store.'}, status=403)

    item_key = request.POST.get('item', '')
    item = STORE_CATALOG.get(item_key)
    if item is None:
        return JsonResponse({'error': 'Unknown item.'}, status=400)

    try:
        quantity = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid quantity.'}, status=400)
    if quantity < 1 or quantity > GIFT_MAX_QUANTITY:
        return JsonResponse({'error': f'Quantity must be between 1 and {GIFT_MAX_QUANTITY}.'}, status=400)

    recipient_username = request.POST.get('recipient', '').strip()
    recipient = CustomUser.objects.filter(username=recipient_username).first()
    if recipient is None:
        return JsonResponse({'error': 'Recipient not found.'}, status=400)
    if recipient == request.user:
        return JsonResponse({'error': 'You cannot gift yourself.'}, status=400)
    if recipient.is_guest:
        return JsonResponse({'error': 'Guest accounts cannot receive gifts.'}, status=400)
    if _is_blocked_pair(request.user, recipient):
        return JsonResponse({'error': 'Gifting is not available between these accounts.'}, status=403)

    source = request.POST.get('source', 'buy')
    if source not in ('buy', 'own'):
        source = 'buy'
    if item['kind'] != 'tokens':
        source = 'buy'  # VIP has no "own balance" to gift from

    payment_method = request.POST.get('payment_method', 'card')
    if payment_method not in ('card', 'paypal', 'cipher_pay'):
        payment_method = 'card'

    note = request.POST.get('note', '').strip()[:500]

    response = {
        'item': item_key,
        'label': item['label'],
        'kind': item['kind'],
        'quantity': quantity,
        'source': source,
        'recipient': recipient.username,
    }

    if item['kind'] == 'tokens':
        total_tokens = item['unit_tokens'] * quantity
        if source == 'own':
            if request.user.currency < total_tokens:
                return JsonResponse({'error': 'You do not have enough Cipher Tokens for this gift.'}, status=400)
            request.user.currency -= total_tokens
            request.user.save(update_fields=['currency'])
            TokenTransaction.objects.create(
                user=request.user,
                kind=TokenTransaction.SPENT,
                amount=-total_tokens,
                balance_after=request.user.currency,
                note=f'Gifted {total_tokens} tokens to {recipient.username}',
            )
            response['sender_balance'] = request.user.currency
            response['total_price_cents'] = 0
        else:
            response['total_price_cents'] = item['unit_price_cents'] * quantity

        recipient.currency += total_tokens
        recipient.save(update_fields=['currency'])
        gift_note = f'Gift from {request.user.username}'
        if note:
            gift_note += f': "{note}"'
        TokenTransaction.objects.create(
            user=recipient,
            kind=TokenTransaction.GIFT,
            amount=total_tokens,
            balance_after=recipient.currency,
            note=gift_note,
        )
        response['total_tokens'] = total_tokens
        gift_desc = f'{total_tokens} Cipher Tokens'
    else:  # 'vip'
        total_days = item['unit_days'] * quantity
        base = recipient.vip_expires_at if recipient.is_vip else timezone.now()
        recipient.vip_expires_at = base + timedelta(days=total_days)
        recipient.save(update_fields=['vip_expires_at'])
        response['total_days'] = total_days
        response['total_price_cents'] = item['unit_price_cents'] * quantity
        gift_desc = f'{total_days} day{"s" if total_days != 1 else ""} of VIP Membership'

    # Only a real (fake-money) spend counts toward the Top Donators
    # leaderboard - "gift from my own balance" paid $0 (response['total_
    # price_cents'] is 0 in that branch above), so it correctly logs
    # nothing here.
    if response['total_price_cents'] > 0:
        PurchaseLog.objects.create(
            user=request.user,
            item_key=item_key,
            label=f'Gift: {item["label"]}',
            quantity=quantity,
            amount_cents=response['total_price_cents'],
        )

    body_lines = [f'\U0001f381 You received a gift from {request.user.username}: {gift_desc}.']
    if note:
        body_lines.append(f'Note: "{note}"')
    conversation = _get_or_create_dm(request.user, recipient)
    Message.objects.create(conversation=conversation, sender=request.user, body='\n'.join(body_lines))
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=['last_message_at'])

    return JsonResponse(response)


@login_required
def profile_edit_view(request):
    """
    Deprecated standalone edit page - editing now happens inline on
    /profile/ itself. Kept as a redirect so the old URL/bookmark still
    goes somewhere sensible instead of 404ing.
    """
    return redirect('profile')
