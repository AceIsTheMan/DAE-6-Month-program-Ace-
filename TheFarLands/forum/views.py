from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import PostForm
from .models import Post, PostReaction


def forum_index_view(request):
    """
    Forum landing page: a feed of Posts, plus a composer visible only to
    the Director role (see accounts.models.CustomUser.is_director) - the
    site's sole Director/Developer account. Reading the feed and reacting
    with a like/dislike stays open to everyone signed in; posting is
    Director-only, enforced here (not just hidden in the template) in
    case of a direct POST from anyone else.
    """
    can_post = request.user.is_authenticated and request.user.is_director
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

    posts = Post.objects.select_related('author').annotate(
        like_total=Count('reactions', filter=Q(reactions__value=PostReaction.LIKE)),
        dislike_total=Count('reactions', filter=Q(reactions__value=PostReaction.DISLIKE)),
    )

    my_reactions = {}
    if request.user.is_authenticated:
        my_reactions = dict(
            PostReaction.objects.filter(post__in=posts, user=request.user).values_list('post_id', 'value')
        )

    return render(request, 'forum/index.html', {
        'posts': posts,
        'form': form,
        'can_post': can_post,
        'my_reactions': my_reactions,
    })


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
