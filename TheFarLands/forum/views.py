import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.models import CustomUser
from mail.models import Conversation, ConversationParticipant, Message, ModerationAction

from .forms import CommentForm, PostForm
from .models import Comment, Post, PostReaction
from .sanitize import sanitize_post_html

COMMENTS_PAGE_SIZE = 5

# @mention token - same shape forum.sanitize.linkify_mentions matches for
# rendering, kept separate here since this one needs its own capture
# group semantics (see _notify_mentioned_users).
_MENTION_TOKEN_RE = re.compile(r'@(\w+)')

# The reserved "everyone" broadcast token (see _broadcast_all_mention) -
# \b after "all" so "@allison" never matches this, only "@all"/"@All"
# exactly (optionally followed by punctuation/whitespace/end of string).
_ALL_MENTION_RE = re.compile(r'@all\b', re.IGNORECASE)


def _notify_mentioned_users(comment, raw_body):
    """A real @mention in a comment gets its target a mail notice - see
    mail.models.Conversation's MENTION category. Deliberately scans the
    RAW pre-sanitize text (not comment.body) so the mention regex only
    ever sees plain text, never markup from the **bold**-style markers a
    Director's own comment might contain. Mail mentions (compose/display)
    are link-only with no notification side effect - this is the one
    place @mentioning someone actually alerts them, per forum being
    "somewhere they can converse or talk to others"."""
    tokens = set(_MENTION_TOKEN_RE.findall(raw_body))
    if not tokens:
        return
    mentioned = CustomUser.objects.filter(username__in=tokens).exclude(pk=comment.author_id)
    for target in mentioned:
        conversation = Conversation.objects.create(category=Conversation.MENTION, created_by=comment.author)
        ConversationParticipant.objects.create(conversation=conversation, user=target)
        Message.objects.create(
            conversation=conversation, sender=comment.author, shared_post=comment.post,
            body=f'{comment.author.username} mentioned you in a comment.',
        )


def _broadcast_all_mention(post):
    """A Director post containing the literal @All token broadcasts it
    into every non-guest account's Inbox - reuses the exact Update
    machinery (mail.views.mail_update_new's recipient set) via a
    shared_post embed, just triggered here instead of a manual Mail
    compose. This hook only ever runs from forum_index_view's already
    Director-gated post branch, so a regular account typing @All in a
    comment can never trigger a broadcast - it just renders as an
    unresolved, inert mention there (there's no real account named
    "all", so forum.sanitize.linkify_mentions never links it either)."""
    if not _ALL_MENTION_RE.search(post.body):
        return
    conversation = Conversation.objects.create(category=Conversation.UPDATE, created_by=post.author)
    recipients = CustomUser.objects.filter(is_guest=False).exclude(pk=post.author.pk)
    ConversationParticipant.objects.bulk_create([
        ConversationParticipant(conversation=conversation, user=u) for u in recipients
    ])
    Message.objects.create(conversation=conversation, sender=post.author, shared_post=post)


def _can_comment(user):
    """Every signed-in account may comment except guest ("Hacker")
    accounts - see accounts.models.CustomUser.is_guest. Unlike reactions,
    which are open to any signed-in user."""
    return user.is_authenticated and not user.is_guest


def _active_ban(user):
    """The active Ban/Perm Ban against `user`, or None - see mail.
    models.ModerationAction. A ban blocks the forum entirely (see
    forum_index_view's F.R.E.D. block screen and every other view here);
    it never touches Home, Mail, or Profile."""
    if not user.is_authenticated:
        return None
    return ModerationAction.active_for(user, [ModerationAction.BAN, ModerationAction.PERM_BAN])


def _require_not_muted_by_moderator(user):
    """A real moderator Mute (mail.models.ModerationAction, not the
    self-service mail.models.UserRelationship.MUTE) blocks posting a
    forum comment - see forum_add_comment_view. Reading/reacting is
    never affected."""
    action = ModerationAction.active_for(user, [ModerationAction.MUTE])
    if action:
        raise PermissionDenied(
            f'This account is muted until '
            f'{action.expires_at.strftime("%m/%d/%Y %I:%M %p") if action.expires_at else "further notice"}.'
        )


def forum_index_view(request):
    """
    Forum landing page: a feed of Posts, plus a composer visible only to
    the Director role (see accounts.models.CustomUser.is_director) - the
    site's sole Director/Developer account. Reading the feed and reacting
    with a like/dislike stays open to everyone signed in; posting is
    Director-only, enforced here (not just hidden in the template) in
    case of a direct POST from anyone else.

    Also handles the search bar: `q` matches keywords within a post's
    body (case-insensitive substring, highlighted client-side by the
    `highlight` template filter - see forum.templatetags.forum_extras),
    `date_from`/`date_to` narrow by when a post was made, and `sort`
    flips the feed between newest-first (default) and oldest-first.
    """
    ban = _active_ban(request.user)
    if ban:
        return render(request, 'forum/fred_blocked.html', {'ban': ban}, status=403)

    can_post = request.user.is_authenticated and request.user.is_director
    can_comment = _can_comment(request.user)
    form = None

    if request.method == 'POST':
        if not can_post:
            raise PermissionDenied('Only the Director can post here.')
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            _broadcast_all_mention(post)
            return redirect('forum')
    elif can_post:
        form = PostForm()

    search_query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    sort = request.GET.get('sort', 'new')
    if sort not in ('new', 'old'):
        sort = 'new'

    posts = Post.objects.filter(is_deleted=False).select_related('author')
    if search_query:
        posts = posts.filter(body__icontains=search_query)
    parsed_from = parse_date(date_from) if date_from else None
    if parsed_from:
        posts = posts.filter(created_at__date__gte=parsed_from)
    parsed_to = parse_date(date_to) if date_to else None
    if parsed_to:
        posts = posts.filter(created_at__date__lte=parsed_to)

    posts = posts.annotate(
        like_total=Count('reactions', filter=Q(reactions__value=PostReaction.LIKE)),
        dislike_total=Count('reactions', filter=Q(reactions__value=PostReaction.DISLIKE)),
        comment_total=Count('comments', distinct=True),
    )
    posts = posts.order_by('created_at') if sort == 'old' else posts.order_by('-created_at')

    my_reactions = {}
    if request.user.is_authenticated:
        my_reactions = dict(
            PostReaction.objects.filter(post__in=posts, user=request.user).values_list('post_id', 'value')
        )

    return render(request, 'forum/index.html', {
        'posts': posts,
        'form': form,
        'can_post': can_post,
        'can_comment': can_comment,
        'my_reactions': my_reactions,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
    })


@login_required
def forum_edit_post_view(request, post_id):
    """
    Edit a post - Director-only, same gate as posting/deleting (see
    forum_index_view / forum_delete_post_view). Bumps `edited_at` so the
    change is visible only to the Director - see Post.edited_at and the
    can_post-gated marker in templates/forum/index.html.
    """
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can edit posts.')
    post = get_object_or_404(Post, pk=post_id)

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            edited = form.save(commit=False)
            edited.edited_at = timezone.now()
            edited.save()
            return redirect(reverse('forum') + f'#post-{post.id}')
    else:
        form = PostForm(instance=post)

    return render(request, 'forum/edit_post.html', {'form': form, 'post': post})


@login_required
def forum_react_view(request, post_id):
    """
    Toggle the signed-in user's like/dislike on a post. Reacting the same
    way again clears it; reacting the other way flips it. Anyone signed
    in may react - only posting is Director-only.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if _active_ban(request.user):
        raise PermissionDenied('This account is banned from the forum.')

    post = get_object_or_404(Post, pk=post_id)
    value = request.POST.get('value')
    if value not in (PostReaction.LIKE, PostReaction.DISLIKE):
        raise PermissionDenied('Invalid reaction.')

    existing = PostReaction.objects.filter(post=post, user=request.user).first()
    if existing and existing.value == value:
        existing.delete()
    elif existing:
        existing.value = value
        existing.save(update_fields=['value'])
    else:
        PostReaction.objects.create(post=post, user=request.user, value=value)

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect('forum')


@login_required
def forum_delete_post_view(request, post_id):
    """Delete a post - Director-only, same gate as posting (see
    forum_index_view), enforced here too in case of a direct POST from
    anyone else. Soft delete only - see Post.is_deleted; the Director
    can Re-Send or permanently purge it from the Chat Logs dashboard
    panel."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can delete posts.')

    post = get_object_or_404(Post, pk=post_id)
    post.is_deleted = True
    post.deleted_at = timezone.now()
    post.deleted_by = request.user
    post.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    return redirect('forum')


def forum_comments_view(request, post_id):
    """
    Return the next page of a post's comments as an HTML fragment - never
    a full page. The comment section's [+] "Load 5 more" button fetches
    this and appends the result (see the script in templates/forum/index.html).
    Read-only, but still gated like the rest of the comment section: guest
    ("Hacker") accounts and signed-out visitors get nothing.
    """
    if not _can_comment(request.user):
        raise PermissionDenied('Comments are not available on this account.')
    if _active_ban(request.user):
        raise PermissionDenied('This account is banned from the forum.')

    post = get_object_or_404(Post, pk=post_id)
    try:
        offset = max(0, int(request.GET.get('offset', 0)))
    except ValueError:
        offset = 0

    comments = post.comments.filter(is_deleted=False).select_related('author')
    total = comments.count()
    next_offset = offset + COMMENTS_PAGE_SIZE

    return render(request, 'forum/_comments_page.html', {
        'comments': comments[offset:next_offset],
        'has_more': next_offset < total,
        'next_offset': next_offset,
        'post_id': post.id,
        # Admin can now delete any comment too (not just the Director) -
        # see forum_delete_comment_view.
        'can_delete_comments': request.user.is_authenticated and request.user.is_moderator,
    })


@login_required
def forum_add_comment_view(request, post_id):
    """Post a comment - any signed-in account except guest ("Hacker")
    accounts, see _can_comment. Same next-url redirect pattern as
    forum_react_view.

    The **bold**-style markers (see forum.sanitize) only turn into real
    formatting for the Director - no new UI for this, everyone else's
    comment is still escaped for safety, just without the marker step, so
    their ** stays literal text instead of becoming <b>.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not _can_comment(request.user):
        raise PermissionDenied('Comments are not available on this account.')
    if _active_ban(request.user):
        raise PermissionDenied('This account is banned from the forum.')
    _require_not_muted_by_moderator(request.user)

    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.body = sanitize_post_html(form.cleaned_data['body'], apply_markers=request.user.is_director)
        comment.save()
        _notify_mentioned_users(comment, form.cleaned_data['body'])

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect('forum')


@login_required
def forum_delete_comment_view(request, comment_id):
    """
    Delete a comment - either its own author (see the comment's dots-menu
    in forum/templates/forum/_comments_page.html), or Admin/Director,
    whose moderation power covers every comment including someone else's
    (see _can_comment for who may add one in the first place). AJAX-only:
    comments are loaded into the page without a full reload, so deleting
    one removes it from the DOM in place instead of redirecting - see the
    script in templates/forum/index.html.

    Soft delete only - see Comment.is_deleted; the Director can Re-Send
    or permanently purge it from the Chat Logs dashboard panel.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    comment = get_object_or_404(Comment, pk=comment_id)
    if comment.author_id != request.user.pk and not request.user.is_moderator:
        raise PermissionDenied('You can only delete your own comments.')

    comment.is_deleted = True
    comment.deleted_at = timezone.now()
    comment.deleted_by = request.user
    comment.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    return HttpResponse(status=204)
