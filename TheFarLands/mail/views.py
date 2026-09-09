from datetime import timedelta

import requests
from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import CustomUser
from forum.models import Post

from .forms import (
    BAN_UNITS,
    GROUP_MAX_MEMBERS,
    MUTE_UNITS,
    REPORT_COOLDOWN_HOURS,
    REPORT_LIMIT,
    DirectiveForm,
    ForumShareForm,
    GroupCreateForm,
    MessageComposeForm,
    ModerationActionForm,
    ReportForm,
    UpdateForm,
    _is_blocked_pair,
)
from .models import Conversation, ConversationParticipant, Message, ModerationAction, Report, UserRelationship


def _require_mail_access(user):
    """Every mail view except mail_report_new requires a signed-in,
    non-guest account - guests can't use any part of Mail. Mirrors
    forum.views._can_comment's "authenticated and not guest" gate,
    enforced here (not just hidden in the template) in case of a direct
    request from a guest account."""
    if not user.is_authenticated or user.is_guest:
        raise PermissionDenied('Mail is not available on this account.')


def _sidebar_context(user, active):
    return {
        'active_category': active,
        'can_moderate': user.is_moderator,
    }


def _require_not_muted_by_moderator(user):
    """A real moderator Mute (see mail.models.ModerationAction - not the
    self-service notification mute) blocks sending anything in Mail:
    Social messages, group creation, DM starts, forum shares. Reading is
    never affected."""
    action = ModerationAction.active_for(user, [ModerationAction.MUTE])
    if action:
        raise PermissionDenied(
            f'This account is muted until '
            f'{action.expires_at.strftime("%m/%d/%Y %I:%M %p") if action.expires_at else "further notice"}.'
        )


def _notify_director_of_moderation_action(action):
    """Drops a DM from the acting moderator to every current Director
    summarizing the action taken - "sent to the directors mail" per the
    feature's requirements. The action itself (mail.models.
    ModerationAction) is already the permanent, immediately-visible
    record moderators review in Report History's Bans/Mutes tab; this
    mail is just the notification trail on top of that, not a gate on
    when the record becomes visible."""
    directors = CustomUser.objects.filter(role=CustomUser.ROLE_DIRECTOR).exclude(pk=action.moderator_id)
    # action.reason is already sanitized (escaped + newlines -> <br>, see
    # ModerationActionForm.clean_reason) - this body is rendered with the
    # `safe` filter same as any other message, so the surrounding text
    # needs a real <br> too, not a literal \n. Usernames are safe as-is:
    # Django's default username validator never allows HTML-special
    # characters.
    summary = (
        f'{action.moderator.username} issued a {action.get_kind_display()} against {action.target.username}.<br>'
        f'Reason: {action.reason}'
    )
    for director in directors:
        conversation = _get_or_create_dm(action.moderator, director)
        Message.objects.create(conversation=conversation, sender=action.moderator, body=summary)
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['last_message_at'])


def _report_cooldown_remaining(user):
    """None if `user` may file another report right now; otherwise the
    timedelta until they can again. Rolling window, not a fixed lockout
    timestamp: once REPORT_LIMIT reports have been filed within the last
    REPORT_COOLDOWN_HOURS, filing is blocked until the OLDEST of those
    reports ages past the window - at which point there are fewer than
    REPORT_LIMIT left in the window again and filing reopens on its own,
    no separate "cooldown ends at" field needed."""
    window_start = timezone.now() - timedelta(hours=REPORT_COOLDOWN_HOURS)
    recent = list(
        Report.objects.filter(reporter=user, created_at__gte=window_start).order_by('created_at')
    )
    if len(recent) < REPORT_LIMIT:
        return None
    oldest_of_the_limit = recent[len(recent) - REPORT_LIMIT]
    return (oldest_of_the_limit.created_at + timedelta(hours=REPORT_COOLDOWN_HOURS)) - timezone.now()


def _get_or_create_dm(user_a, user_b):
    """Get-or-create the 2-participant SOCIAL conversation between these
    two accounts - a DM is just a Conversation shaped that way, see
    mail.models.Conversation's docstring."""
    existing = (
        Conversation.objects.filter(category=Conversation.SOCIAL, participants=user_a)
        .filter(participants=user_b)
        .annotate(member_count=Count('participants'))
        .filter(member_count=2)
        .first()
    )
    if existing:
        return existing
    conversation = Conversation.objects.create(category=Conversation.SOCIAL, created_by=user_a)
    ConversationParticipant.objects.create(conversation=conversation, user=user_a, last_read_at=timezone.now())
    ConversationParticipant.objects.create(conversation=conversation, user=user_b)
    return conversation


@login_required
def mail_inbox(request):
    """Aggregated feed: every category this user participates in,
    generalized into one list - the "director-only inbox" the requirements
    initially named turned out to mean the Reports category being
    Director/Admin-only (see mail_reports below), not a second inbox."""
    _require_mail_access(request.user)
    messages_list = (
        Message.objects.filter(conversation__participants=request.user)
        .exclude(sender=request.user)
        .select_related('conversation', 'sender', 'shared_post')
        .order_by('-created_at')[:100]
    )
    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'inbox'),
        'messages_list': messages_list,
    })


@login_required
def mail_sent(request):
    _require_mail_access(request.user)
    messages_list = (
        Message.objects.filter(sender=request.user)
        .select_related('conversation', 'shared_post')
        .order_by('-created_at')[:100]
    )
    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'sent'),
        'messages_list': messages_list,
    })


@login_required
def mail_updates(request):
    """Read-only for recipients - no reply endpoint exists for UPDATE
    conversations."""
    _require_mail_access(request.user)
    messages_list = (
        Message.objects.filter(conversation__category=Conversation.UPDATE, conversation__participants=request.user)
        .select_related('conversation', 'sender')
        .order_by('-created_at')[:100]
    )
    ConversationParticipant.objects.filter(
        user=request.user, conversation__category=Conversation.UPDATE
    ).update(last_read_at=timezone.now())
    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'updates'),
        'messages_list': messages_list,
    })


@login_required
def mail_update_new(request):
    """Director-only broadcast to every current non-guest account - see
    mail.forms.UpdateForm's docstring on why this has no recipient
    picker."""
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can send an Update.')
    if request.method == 'POST':
        form = UpdateForm(request.POST)
        if form.is_valid():
            conversation = Conversation.objects.create(category=Conversation.UPDATE, created_by=request.user)
            recipients = CustomUser.objects.filter(is_guest=False).exclude(pk=request.user.pk)
            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conversation, user=u) for u in recipients
            ])
            Message.objects.create(conversation=conversation, sender=request.user, body=form.cleaned_data['body'])
            return redirect('mail_updates')
    else:
        form = UpdateForm()
    return render(request, 'mail/broadcast_new.html', {'form': form, 'kind': 'Update'})


@login_required
def mail_directives(request):
    """Received Directives - no delete/dismiss route exists anywhere for
    this category. That absence is the entire "cannot be ignored"
    enforcement (see mail.models.Conversation's docstring)."""
    _require_mail_access(request.user)
    messages_list = (
        Message.objects.filter(conversation__category=Conversation.DIRECTIVE, conversation__participants=request.user)
        .select_related('conversation', 'sender')
        .order_by('-created_at')[:100]
    )
    ConversationParticipant.objects.filter(
        user=request.user, conversation__category=Conversation.DIRECTIVE
    ).update(last_read_at=timezone.now())
    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'directives'),
        'messages_list': messages_list,
    })


@login_required
def mail_directive_new(request):
    """Director-only send to one or more specific recipients - see
    mail.forms.DirectiveForm."""
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can send a Directive.')
    if request.method == 'POST':
        form = DirectiveForm(request.POST, sender=request.user)
        if form.is_valid():
            recipients = form.cleaned_data['usernames']
            conversation = Conversation.objects.create(category=Conversation.DIRECTIVE, created_by=request.user)
            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conversation, user=u) for u in recipients
            ])
            Message.objects.create(conversation=conversation, sender=request.user, body=form.cleaned_data['body'])
            return redirect('mail_directives')
    else:
        form = DirectiveForm(sender=request.user)
    return render(request, 'mail/broadcast_new.html', {'form': form, 'kind': 'Directive', 'recipient_mode': 'directive'})


@login_required
def mail_social(request):
    _require_mail_access(request.user)
    conversations = (
        Conversation.objects.filter(category=Conversation.SOCIAL, participants=request.user)
        .prefetch_related('memberships__user')
        .order_by('-last_message_at')
    )
    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'social'),
        'conversations': conversations,
    })


@login_required
def mail_social_thread(request, conversation_id):
    _require_mail_access(request.user)
    conversation = get_object_or_404(Conversation, pk=conversation_id, category=Conversation.SOCIAL)
    membership = get_object_or_404(ConversationParticipant, conversation=conversation, user=request.user)

    if not conversation.is_group:
        # Retroactive block enforcement for an existing DM - "prevent
        # that user from ... interacting with them completely" means a
        # block also closes off a conversation that already existed, not
        # just new ones (see mail.forms._is_blocked_pair for the
        # moderator exemption this respects automatically).
        other = conversation.memberships.exclude(user=request.user).select_related('user').first()
        if other and _is_blocked_pair(request.user, other.user):
            raise PermissionDenied('This conversation is not available between these accounts.')

    if request.method == 'POST':
        _require_not_muted_by_moderator(request.user)
        form = MessageComposeForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=['last_message_at'])
            membership.last_read_at = timezone.now()
            membership.save(update_fields=['last_read_at'])
            return redirect('mail_social_thread', conversation_id=conversation.id)
    else:
        form = MessageComposeForm()
        membership.last_read_at = timezone.now()
        membership.save(update_fields=['last_read_at'])

    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'social'),
        'conversations': Conversation.objects.filter(
            category=Conversation.SOCIAL, participants=request.user
        ).order_by('-last_message_at'),
        'open_conversation': conversation,
        'thread_messages': conversation.messages.select_related('sender', 'shared_post', 'shared_post__author'),
        'members': ConversationParticipant.objects.filter(conversation=conversation).select_related('user'),
        'form': form,
        'member_cap': GROUP_MAX_MEMBERS,
    })


@login_required
def mail_social_dm_start(request, username):
    _require_mail_access(request.user)
    target = get_object_or_404(CustomUser, username=username)
    if target == request.user:
        raise PermissionDenied('You cannot message yourself.')
    if target.is_guest:
        raise PermissionDenied('Guest accounts cannot be messaged.')
    if _is_blocked_pair(request.user, target):
        raise PermissionDenied('Messaging is not available between these accounts.')
    _require_not_muted_by_moderator(request.user)
    conversation = _get_or_create_dm(request.user, target)
    return redirect('mail_social_thread', conversation_id=conversation.id)


@login_required
def mail_group_new(request):
    _require_mail_access(request.user)
    if request.method == 'POST':
        _require_not_muted_by_moderator(request.user)
        form = GroupCreateForm(request.POST, sender=request.user)
        if form.is_valid():
            recipients = form.cleaned_data['usernames']
            conversation = Conversation.objects.create(
                category=Conversation.SOCIAL,
                created_by=request.user,
                title=form.cleaned_data.get('title', ''),
                is_group=True,
            )
            ConversationParticipant.objects.create(
                conversation=conversation, user=request.user, last_read_at=timezone.now()
            )
            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conversation, user=u) for u in recipients
            ])
            return redirect('mail_social_thread', conversation_id=conversation.id)
    else:
        form = GroupCreateForm(sender=request.user)
    return render(request, 'mail/group_new.html', {
        'form': form,
        'group_max_members': GROUP_MAX_MEMBERS,
        'group_invite_max': GROUP_MAX_MEMBERS - 1,
    })


@login_required
def mail_friends(request):
    """List of accounts this user has friended - see mail.models.
    UserRelationship's docstring (instant friend, no accept step, so this
    is simply "everyone I've friended," not a mutual-friends concept)."""
    _require_mail_access(request.user)
    friends = (
        UserRelationship.objects.filter(from_user=request.user, kind=UserRelationship.FRIEND)
        .select_related('to_user')
        .order_by('to_user__username')
    )
    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'friends'),
        'friends': friends,
    })


@login_required
def mail_reports(request):
    _require_mail_access(request.user)
    if not request.user.is_moderator:
        raise PermissionDenied('Only Director/Admin accounts can view Reports.')
    reports = Report.objects.filter(status=Report.OPEN).select_related(
        'reporter', 'reported_user', 'reported_message', 'reported_message__sender'
    )
    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'reports'),
        'reports': reports,
    })


@login_required
def mail_report_history(request):
    """Two sub-tabs, both Director/Admin only: 'reports' (every report
    that's been Resolved or Dismissed - moved here off the live Reports
    queue once mail_report_resolve fires, so that queue only ever shows
    what's still open) and 'actions' (every Mute/Ban/Perm Ban ever
    issued - mail.models.ModerationAction is the permanent record; this
    is where moderators review each other's actions and why, alongside
    the DM notification mail.views._notify_director_of_moderation_action
    sends). `q` filters either tab by username - reporter/reported_user
    on 'reports', moderator/target on 'actions'."""
    _require_mail_access(request.user)
    if not request.user.is_moderator:
        raise PermissionDenied('Only Director/Admin accounts can view Report History.')

    tab = request.GET.get('tab', 'reports')
    if tab not in ('reports', 'actions'):
        tab = 'reports'
    query = request.GET.get('q', '').strip()

    reports = None
    actions = None
    if tab == 'actions':
        actions = ModerationAction.objects.select_related('moderator', 'target', 'lifted_by')
        if query:
            actions = actions.filter(Q(moderator__username__icontains=query) | Q(target__username__icontains=query))
    else:
        reports = Report.objects.exclude(status=Report.OPEN).select_related(
            'reporter', 'reported_user', 'reported_message', 'reported_message__sender', 'resolved_by'
        ).order_by('-resolved_at')
        if query:
            reports = reports.filter(Q(reporter__username__icontains=query) | Q(reported_user__username__icontains=query))

    return render(request, 'mail/index.html', {
        **_sidebar_context(request.user, 'report_history'),
        'history_tab': tab,
        'history_query': query,
        'reports': reports,
        'actions': actions,
    })


@login_required
def mail_report_resolve(request, report_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_moderator:
        raise PermissionDenied('Only Director/Admin accounts can resolve reports.')
    report = get_object_or_404(Report, pk=report_id)
    status = request.POST.get('status', Report.RESOLVED)
    if status not in (Report.RESOLVED, Report.DISMISSED):
        status = Report.RESOLVED
    report.status = status
    report.resolved_by = request.user
    report.resolved_at = timezone.now()
    report.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    return HttpResponse(status=204)


@login_required
def mail_moderation_new(request, username):
    """Director/Admin issuing a Mute/Ban/Perm Ban against `username` -
    see mail.forms.ModerationActionForm for the duration-unit rules per
    kind. The Director can never be targeted (accounts.models.CustomUser.
    is_director), mirroring the "block is futile against a moderator"
    exemption elsewhere in this app - moderation power only ever flows
    downward. A reason is mandatory no matter which kind this is."""
    if not request.user.is_moderator:
        raise PermissionDenied('Only Director/Admin accounts can take moderation action.')
    target = get_object_or_404(CustomUser, username=username)
    if target.is_director:
        raise PermissionDenied('The Director cannot be moderated.')
    if target == request.user:
        raise PermissionDenied('You cannot moderate yourself.')

    if request.method == 'POST':
        form = ModerationActionForm(request.POST)
        if form.is_valid():
            duration = form.cleaned_data['duration']
            action = ModerationAction.objects.create(
                moderator=request.user,
                target=target,
                kind=form.cleaned_data['kind'],
                reason=form.cleaned_data['reason'],
                expires_at=(timezone.now() + duration) if duration else None,
            )
            _notify_director_of_moderation_action(action)
            flash.success(request, f'{action.get_kind_display()} issued against {target.username}.')
            return redirect('user_profile', username=target.username)
    else:
        form = ModerationActionForm()

    return render(request, 'mail/moderation_new.html', {
        'form': form,
        'target': target,
        'mute_units': sorted(MUTE_UNITS),
        'ban_units': sorted(BAN_UNITS, key=lambda u: ['weeks', 'months', 'years'].index(u)),
    })


@login_required
def mail_moderation_lift(request, action_id):
    """Early Unmute/Unban - also how a Perm Ban ever ends, since it has
    no expires_at to age out on its own."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_moderator:
        raise PermissionDenied('Only Director/Admin accounts can lift a moderation action.')
    action = get_object_or_404(ModerationAction, pk=action_id)
    action.lifted_at = timezone.now()
    action.lifted_by = request.user
    action.save(update_fields=['lifted_at', 'lifted_by'])
    return HttpResponse(status=204)


@login_required
def mail_report_new(request):
    """Full-page report form (mail/templates/mail/report_new.html) -
    replaces the old modal entirely. Deliberately NOT gated by
    _require_mail_access - reporting is open to guest accounts too (see
    mail.models.Report's docstring), it's the one mail-adjacent action
    that isn't a "Mail" privilege.

    Target is resolved from `target_type`('user'/'message') + `target_id`
    - as GET query params when arriving from a Report link (see
    _dots_menu.html, prefilled from a profile page or a Social message),
    or as POST fields once the on-page username search (see
    mail/_recipient_picker_scripts.html's single-select mode) has picked
    someone with no message/profile context at hand.
    """
    target_type = request.POST.get('target_type') or request.GET.get('target_type', '')
    target_id = request.POST.get('target_id') or request.GET.get('target_id', '')

    reported_user = None
    reported_message = None
    if target_type == 'user' and target_id:
        reported_user = CustomUser.objects.filter(pk=target_id).first()
    elif target_type == 'message' and target_id:
        reported_message = Message.objects.select_related('sender').filter(pk=target_id).first()

    cooldown = _report_cooldown_remaining(request.user)
    cooldown_hours_left = int(cooldown.total_seconds() // 3600) + 1 if cooldown else None

    if request.method == 'POST':
        form = ReportForm(request.POST, request.FILES)
        if cooldown:
            flash.error(
                request,
                f'You\'ve filed {REPORT_LIMIT} reports in the last {REPORT_COOLDOWN_HOURS} hours - '
                f'try again in about {cooldown_hours_left} hour(s).',
            )
        elif not reported_user and not reported_message:
            flash.error(request, 'Pick who or what you\'re reporting first.')
        elif form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.reported_user = reported_user
            report.reported_message = reported_message
            report.save()
            flash.success(request, 'Report filed - a moderator will review it.')
            return redirect('mail_inbox' if not request.user.is_guest else 'home')
    else:
        form = ReportForm()

    return render(request, 'mail/report_new.html', {
        'form': form,
        'target_type': target_type,
        'target_id': target_id,
        'reported_user': reported_user,
        'reported_message': reported_message,
        'cooldown_hours_left': cooldown_hours_left,
        'report_limit': REPORT_LIMIT,
        'report_cooldown_hours': REPORT_COOLDOWN_HOURS,
    })


@login_required
def mail_recipient_search(request):
    """AJAX username search backing every recipient picker (New Group,
    Directive send, Forum Share, and the report page's username search).

    `mode=directive` skips the block-filter so a Director can always
    reach anyone, and requires the requester actually be the Director.
    `mode=report` is the least restrictive: no guest-exclusion (a guest
    account can absolutely be the subject of a report) and no
    block-filter (blocking someone shouldn't hide them from being
    reported) - just "who is this account," which is also why it's the
    only mode that doesn't require _require_mail_access (reporting is
    open to guests too, see mail.models.Report's docstring)."""
    query = request.GET.get('q', '').strip()
    mode = request.GET.get('mode', 'social')
    if mode == 'report':
        if not request.user.is_authenticated:
            raise PermissionDenied('You must be signed in to search.')
    else:
        _require_mail_access(request.user)
    if mode == 'directive' and not request.user.is_director:
        raise PermissionDenied('Only the Director can search recipients in Directive mode.')

    users = CustomUser.objects.exclude(pk=request.user.pk)
    if query:
        users = users.filter(username__icontains=query)
    if mode not in ('directive', 'report'):
        users = users.filter(is_guest=False)
        blocked_pairs = UserRelationship.objects.filter(kind=UserRelationship.BLOCK).filter(
            Q(from_user=request.user) | Q(to_user=request.user)
        ).values_list('from_user_id', 'to_user_id')
        blocked_ids = {uid for pair in blocked_pairs for uid in pair if uid != request.user.pk}
        users = users.exclude(pk__in=blocked_ids)
    users = users.order_by('username')[:20]
    return JsonResponse({'results': [
        {
            'id': u.id,
            'username': u.username,
            'profile_picture_url': u.profile_picture.url if u.profile_picture else None,
        }
        for u in users
    ]})


@login_required
def mail_forum_share(request, post_id):
    _require_mail_access(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if request.method == 'POST':
        _require_not_muted_by_moderator(request.user)
        form = ForumShareForm(request.POST, sender=request.user)
        if form.is_valid():
            for target in form.cleaned_data['usernames']:
                conversation = _get_or_create_dm(request.user, target)
                Message.objects.create(conversation=conversation, sender=request.user, shared_post=post)
                conversation.last_message_at = timezone.now()
                conversation.save(update_fields=['last_message_at'])
            return HttpResponse(status=204)
        return HttpResponse(status=400)
    form = ForumShareForm(sender=request.user)
    return render(request, 'mail/_recipient_picker.html', {
        'form': form, 'share_post_id': post.id, 'picker_title': 'Share this post',
    })


@login_required
def mail_gif_search(request):
    """Server-side Tenor proxy - the API key never reaches the browser,
    and only a trimmed result list is forwarded, never Tenor's raw
    response. Returns an empty result list (not an error) if no key is
    configured or the request fails, so the compose box degrades
    gracefully instead of breaking."""
    _require_mail_access(request.user)
    query = request.GET.get('q', '').strip()
    api_key = getattr(settings, 'TENOR_API_KEY', '')
    if not query or not api_key:
        return JsonResponse({'results': []})
    try:
        response = requests.get(
            'https://tenor.googleapis.com/v2/search',
            params={'q': query, 'key': api_key, 'limit': 20, 'client_key': 'thefarlands', 'media_filter': 'gif'},
            timeout=3,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return JsonResponse({'results': []})

    results = []
    for item in data.get('results', []):
        formats = item.get('media_formats', {})
        gif = formats.get('gif') or formats.get('tinygif')
        if not gif:
            continue
        preview = formats.get('tinygif') or gif
        results.append({'id': item.get('id'), 'url': gif.get('url'), 'preview_url': preview.get('url')})
    return JsonResponse({'results': results})


@login_required
def mail_relationship_friend(request, username):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    target = get_object_or_404(CustomUser, username=username)
    if target == request.user:
        raise PermissionDenied('You cannot friend yourself.')
    existing = UserRelationship.objects.filter(
        from_user=request.user, to_user=target, kind=UserRelationship.FRIEND
    ).first()
    if existing:
        existing.delete()
        friended = False
    else:
        UserRelationship.objects.create(from_user=request.user, to_user=target, kind=UserRelationship.FRIEND)
        friended = True
    return JsonResponse({'friended': friended})


@login_required
def mail_relationship_mute(request, username):
    """Toggle muting notifications from `username` - unlike Block, this
    is purely a notification-badge suppression (see mail.context_
    processors.notification_counts), never a messaging/search
    restriction; the muted account can interact completely normally."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    target = get_object_or_404(CustomUser, username=username)
    if target == request.user:
        raise PermissionDenied('You cannot mute yourself.')
    existing = UserRelationship.objects.filter(
        from_user=request.user, to_user=target, kind=UserRelationship.MUTE
    ).first()
    if existing:
        existing.delete()
        muted = False
    else:
        UserRelationship.objects.create(from_user=request.user, to_user=target, kind=UserRelationship.MUTE)
        muted = True
    return JsonResponse({'muted': muted})


@login_required
def mail_relationship_block(request, username):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    target = get_object_or_404(CustomUser, username=username)
    if target == request.user:
        raise PermissionDenied('You cannot block yourself.')
    existing = UserRelationship.objects.filter(
        from_user=request.user, to_user=target, kind=UserRelationship.BLOCK
    ).first()
    if existing:
        existing.delete()
        blocked = False
    else:
        UserRelationship.objects.create(from_user=request.user, to_user=target, kind=UserRelationship.BLOCK)
        blocked = True
    return JsonResponse({'blocked': blocked})
