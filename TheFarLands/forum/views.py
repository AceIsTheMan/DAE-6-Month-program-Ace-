from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .forms import PostForm
from .models import Post


def forum_index_view(request):
    """
    Forum landing page: a feed of Posts, plus a composer visible only to
    the Director role (see accounts.models.CustomUser.is_director).
    Reading the feed stays open to everyone; posting is Director-only,
    enforced here (not just hidden in the template) in case of a direct
    POST from anyone else.
    """
    can_post = request.user.is_authenticated and request.user.is_director
    form = None

    if request.method == 'POST':
        if not can_post:
            raise PermissionDenied("Only the Director can post here.")
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('forum')
    elif can_post:
        form = PostForm()

    posts = Post.objects.select_related('author').all()

    return render(request, 'forum/index.html', {
        'posts': posts,
        'form': form,
        'can_post': can_post,
    })
