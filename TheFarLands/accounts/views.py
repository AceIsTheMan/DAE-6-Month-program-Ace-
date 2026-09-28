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
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from forum.models import Comment, Post
from mail.models import FriendRequest, Message, ModerationAction, Report, RoleChangeLog, Warning

from .forms import GuestRegisterForm, ProfileEditForm, RegisterForm
from .models import CustomUser

# kind (used in the Chat Logs URLs/template) -> (model, author/sender field name)
CHAT_LOG_MODELS = {
    'post': (Post, 'author'),
    'comment': (Comment, 'author'),
    'message': (Message, 'sender'),
}


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
    """
    force_rules_gate = request.session.pop('force_rules_gate', False)
    return render(request, 'home.html', {'force_rules_gate': force_rules_gate})


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
    (still a stub, "does nothing yet" same as the Currency/"Digit" balance
    in the notification dropdown), Dashboard (Admin/Director-only entry
    point into moderator tools, including a by-username account search
    with warn/mute/ban counts), and three Director-only tabs: Chat Logs
    (soft-deleted Post/Comment/Message, Re-Send/Purge), Admin Logs (an
    audit trail of what Admin-role accounts have done - see
    _admin_activity_entries), and All Users (every account on the site
    with its full account info). Every gated tab is checked server-side,
    not just hidden by the tab UI - same convention as every other
    moderator-only view (see accounts.models.CustomUser.is_moderator/
    is_director).
    """
    active_tab = request.GET.get('tab', 'settings')
    if active_tab == 'dashboard' and not request.user.is_moderator:
        active_tab = 'settings'
    if active_tab in ('logs', 'admin_logs', 'users') and not request.user.is_director:
        active_tab = 'settings'

    context = {'active_tab': active_tab}
    if active_tab == 'dashboard':
        context.update({
            'total_accounts': CustomUser.objects.count(),
            'guest_accounts': CustomUser.objects.filter(is_guest=True).count(),
            'open_reports': Report.objects.filter(status=Report.OPEN).count(),
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
        entries = []
        for kind, (model, author_field) in CHAT_LOG_MODELS.items():
            qs = model.objects.filter(is_deleted=True).select_related(author_field, 'deleted_by')
            for obj in qs:
                entries.append({
                    'kind': kind,
                    'id': obj.pk,
                    'author': getattr(obj, author_field),
                    'body': obj.body,
                    'deleted_at': obj.deleted_at,
                    'deleted_by': obj.deleted_by,
                })
        entries.sort(key=lambda e: e['deleted_at'], reverse=True)
        context['log_entries'] = entries
    elif active_tab == 'admin_logs':
        context['admin_log_entries'] = _admin_activity_entries()
    return render(request, 'settings.html', context)


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
