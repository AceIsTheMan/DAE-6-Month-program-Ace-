from django.shortcuts import render


def forum_index_view(request):
    """
    Forum landing page. Placeholder for now - this is the first piece of
    the Community & Moderation month (September): threads, posts, and
    moderation tools land in this app as the month progresses. For now it
    just needs to exist so the FORUM nav tab (see accounts/templates/
    base.html and home.html) has somewhere real to go instead of 404ing.
    """
    return render(request, 'forum/index.html')
