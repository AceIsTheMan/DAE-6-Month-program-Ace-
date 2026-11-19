from django.utils import timezone

from .models import CustomUser, GuestArchive


class GuestExpiryMiddleware:
    """
    Enforces the guest ("Hacker") trial: on every request, any guest
    account whose trial has run out gets deleted outright - the account
    and everything tied to it (their reactions, etc.), so the account and
    its login are really gone. But not without a trace: each one gets a
    GuestArchive row snapshotted first, so there's still a historical
    record of who they were and when they were here even though the
    account itself is deleted. If the person making the request happens
    to be the guest who just got deleted, Django's own auth machinery
    quietly treats them as logged out from here on - it looks up the user
    by id on each request and won't find one that no longer exists, so no
    extra code is needed for that part.

    Good enough for a small project like this one, checking on every
    request; a busier site would instead run this as a scheduled command
    (e.g. `python3 manage.py clearsessions`-style) rather than inline here.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cutoff = timezone.now() - timezone.timedelta(days=CustomUser.GUEST_TRIAL_DAYS)
        expired = list(CustomUser.objects.filter(is_guest=True, date_joined__lt=cutoff))

        for guest in expired:
            GuestArchive.objects.create(
                original_user_id=guest.id,
                username=guest.username,
                alias=guest.alias,
                rank=guest.rank,
                bio=guest.bio,
                profile_picture_path=guest.profile_picture.name if guest.profile_picture else '',
                date_joined=guest.date_joined,
                last_login=guest.last_login,
                reaction_count=guest.forum_reactions.count(),
            )

        if expired:
            CustomUser.objects.filter(pk__in=[guest.pk for guest in expired]).delete()

        return self.get_response(request)


class DirectorViewAsMiddleware:
    """
    Lets the Director preview the whole site as a Hacker (guest), Agent or
    Admin - picked from their own profile page (see accounts.views.
    director_view_as). The chosen rank lives only in the session; on each
    request it's swapped onto request.user in memory (role, plus is_guest
    for Hacker), so every role check across the site - views, templates,
    the AI assistant's tone - sees that rank. The account's real role is
    never changed: CustomUser.save() refuses to write the previewed values,
    and DB queries (GuestExpiryMiddleware's included) still see the real
    Director. Logging out clears the session, and with it the preview.
    """
    SESSION_KEY = 'director_view_as'
    PREVIEW_ROLES = (CustomUser.ROLE_HACKER, CustomUser.ROLE_AGENT, CustomUser.ROLE_ADMIN)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        view_as = request.session.get(self.SESSION_KEY)
        if view_as:
            user = request.user
            if user.is_authenticated and user.role == CustomUser.ROLE_DIRECTOR and view_as in self.PREVIEW_ROLES:
                user._view_as_real = (user.role, user.is_guest)
                user.role = view_as
                user.is_guest = view_as == CustomUser.ROLE_HACKER
            else:
                # Not (or no longer) the Director - drop the stale preview.
                request.session.pop(self.SESSION_KEY, None)
        return self.get_response(request)
