from django.utils import timezone

from .models import CustomUser


class GuestExpiryMiddleware:
    """
    Enforces the guest ("Hacker") trial: on every request, any guest
    account whose trial has run out gets deleted outright - the account
    and everything tied to it, per "shuts the guest account down and it's
    history." If the person making the request happens to be the guest who
    just got deleted, Django's own auth machinery quietly treats them as
    logged out from here on - it looks up the user by id on each request
    and won't find one that no longer exists, so no extra code is needed
    for that part.

    Good enough for a small project like this one, checking on every
    request; a busier site would instead run this as a scheduled command
    (e.g. `python3 manage.py clearsessions`-style) rather than inline here.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cutoff = timezone.now() - timezone.timedelta(days=CustomUser.GUEST_TRIAL_DAYS)
        CustomUser.objects.filter(is_guest=True, date_joined__lt=cutoff).delete()
        return self.get_response(request)
