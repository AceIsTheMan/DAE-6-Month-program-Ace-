from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CommentForm, PostForm
from .models import Comment, Post, PostReaction
from .sanitize import sanitize_post_html

COMMENTS_PAGE_SIZE = 5


def _can_comment(user):
    """Every signed-in account may comment except guest ("Hacker")
    accounts - see accounts.models.CustomUser.is_guest. Unlike reactions,
    which are open to any signed-in user."""
    return user.is_authenticated and not user.is_guest


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
            return redirect('forum')
    elif can_post:
        form = PostForm()

    search_query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    sort = request.GET.get('sort', 'new')
    if sort not in ('new', 'old'):
        sort = 'new'

    posts = Post.objects.select_related('author')
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
    anyone else."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can delete posts.')

    post = get_object_or_404(Post, pk=post_id)
    post.delete()
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

    post = get_object_or_404(Post, pk=post_id)
    try:
        offset = max(0, int(request.GET.get('offset', 0)))
    except ValueError:
        offset = 0

    comments = post.comments.select_related('author')
    total = comments.count()
    next_offset = offset + COMMENTS_PAGE_SIZE

    return render(request, 'forum/_comments_page.html', {
        'comments': comments[offset:next_offset],
        'has_more': next_offset < total,
        'next_offset': next_offset,
        'post_id': post.id,
        # Also doubles as "is this viewer the Director" for
        # _comments_page.html's redact_for_viewer filter - both gates are
        # the exact same check, so one flag covers both.
        'can_delete_comments': request.user.is_authenticated and request.user.is_director,
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

    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.body = sanitize_post_html(form.cleaned_data['body'], apply_markers=request.user.is_director)
        comment.save()

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect('forum')


@login_required
def forum_delete_comment_view(request, comment_id):
    """
    Delete a comment - Director-only, and unlike everything else the
    Director can moderate, this covers every comment including their own
    (see _can_comment for who may add one in the first place). AJAX-only:
    comments are loaded into the page without a full reload, so deleting
    one removes it from the DOM in place instead of redirecting - see the
    script in templates/forum/index.html.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_director:
        raise PermissionDenied('Only the Director can delete comments.')

    comment = get_object_or_404(Comment, pk=comment_id)
    comment.delete()
    return HttpResponse(status=204)
