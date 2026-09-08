import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import CustomUser
from forum.models import Post

from .forms import (
    GROUP_MAX_MEMBERS,
    DirectiveForm,
    ForumShareForm,
    GroupCreateForm,
    MessageComposeForm,
    ReportForm,
    UpdateForm,
    _is_blocked_pair,
)
from .models import Conversation, ConversationParticipant, Message, Report, UserRelationship


def _require_mail_access(user):
    """Every mail view except mail_report_create requires a signed-in,
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

    if request.method == 'POST':
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
    conversation = _get_or_create_dm(request.user, target)
    return redirect('mail_social_thread', conversation_id=conversation.id)


@login_required
def mail_group_new(request):
    _require_mail_access(request.user)
    if request.method == 'POST':
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
def mail_report_create(request):
    """The one mail view that deliberately allows guest accounts through
    - reporting is a safety valve, not a privilege (see mail.models.
    Report's docstring)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    reported_user_id = request.POST.get('reported_user_id')
    reported_message_id = request.POST.get('reported_message_id')
    if not reported_user_id and not reported_message_id:
        return HttpResponse(status=400)
    form = ReportForm(request.POST)
    if not form.is_valid():
        return HttpResponse(status=400)
    report = form.save(commit=False)
    report.reporter = request.user
    if reported_user_id:
        report.reported_user = get_object_or_404(CustomUser, pk=reported_user_id)
    if reported_message_id:
        report.reported_message = get_object_or_404(Message, pk=reported_message_id)
    report.save()
    return HttpResponse(status=204)


@login_required
def mail_recipient_search(request):
    """AJAX username search backing every recipient picker (New Group,
    Directive send, Forum Share). `mode=directive` skips the block-filter
    so a Director can always reach anyone, and requires the requester
    actually be the Director."""
    _require_mail_access(request.user)
    query = request.GET.get('q', '').strip()
    mode = request.GET.get('mode', 'social')
    if mode == 'directive' and not request.user.is_director:
        raise PermissionDenied('Only the Director can search recipients in Directive mode.')

    users = CustomUser.objects.exclude(pk=request.user.pk)
    if query:
        users = users.filter(username__icontains=query)
    if mode != 'directive':
        users = users.filter(is_guest=False)
        blocked_pairs = UserRelationship.objects.filter(kind=UserRelationship.BLOCK).filter(
            Q(from_user=request.user) | Q(to_user=request.user)
        ).values_list('from_user_id', 'to_user_id')
        blocked_ids = {uid for pair in blocked_pairs for uid in pair if uid != request.user.pk}
        users = users.exclude(pk__in=blocked_ids)
    users = users.order_by('username')[:20]
    return JsonResponse({'results': [{'id': u.id, 'username': u.username} for u in users]})


@login_required
def mail_forum_share(request, post_id):
    _require_mail_access(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if request.method == 'POST':
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
