from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Log in with your username (as always) OR your email as a backup
    username. Email only works when exactly one account uses it."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None or not username or '@' not in username:
            return user
        # Emails aren't unique on CustomUser, so never guess between two
        # accounts - [:2] is enough to tell "exactly one" from "more".
        matches = list(get_user_model().objects.filter(email__iexact=username)[:2])
        if len(matches) != 1:
            return None
        user = matches[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
