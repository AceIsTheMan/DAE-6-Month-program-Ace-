from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from forum.models import Comment, Post
from mail.models import FriendRequest, Message, ModerationAction, Report, RoleChangeLog, UserRelationship, Warning

from .forms import GuestRegisterForm, ProfileEditForm, RegisterForm
from .models import CustomUser, GuestArchive

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

    return render(request, 'home.html', {
        'force_rules_gate': force_rules_gate,
        'role_cutscene_to_play': role_cutscene,
        'director_profile_picture_url': director_profile_picture_url,
        'guest_trial_remaining': guest_trial_remaining,
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
    expired-guest archive - see accounts.models.GuestArchive), and three
    Director-only tabs: Chat Logs (the soft-deleted Post/Comment/Message
    queue, Re-Send/Purge, by default - or, once a keyword/username/date
    filter is used, a search across ALL Post/Comment/Message content,
    deleted or not - see _chat_log_matches), Admin Logs (an audit trail
    of what Admin-role accounts have done - see
    _admin_activity_entries), and All Users (every account on the site
    with its full account info). Every gated tab is checked server-side,
    not just hidden by the tab UI - same convention as every other
    moderator-only view (see accounts.models.CustomUser.is_moderator/
    is_director).

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
    """
    active_tab = request.GET.get('tab', 'settings')
    if active_tab == 'dashboard' and not request.user.is_moderator:
        active_tab = 'settings'
    if active_tab in ('logs', 'admin_logs', 'users') and not request.user.is_director:
        active_tab = 'settings'

    context = {'active_tab': active_tab}
    if active_tab == 'settings':
        active_sub_tab = request.GET.get('sub', 'profile')
        if active_sub_tab not in ('profile', 'blocked', 'notifications', 'cutscenes'):
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


@login_required
def profile_edit_view(request):
    """
    Deprecated standalone edit page - editing now happens inline on
    /profile/ itself. Kept as a redirect so the old URL/bookmark still
    goes somewhere sensible instead of 404ing.
    """
    return redirect('profile')
