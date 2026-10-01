from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import CustomUser


@receiver(user_logged_in)
def force_rules_gate_on_login(sender, request, user, **kwargs):
    """
    Make the "BE ADVISED" rules popup show again immediately after any
    login (regular, via /login/, or guest, via guest_register_view's direct
    login() call) - even if this browser tab already dismissed the popup
    earlier as an anonymous visitor. TFL.js's sessionStorage-based "already
    seen it" suppression is otherwise correct (it's what stops the popup
    reappearing on an ordinary refresh) - it just isn't supposed to survive
    a login event. home_view reads and clears (pops) this flag on the very
    next page render, so it only affects that one load right after login.
    """
    request.session['force_rules_gate'] = True


@receiver(user_logged_in)
def queue_role_cutscene_on_login(sender, request, user, **kwargs):
    """
    Picks which role-based terminal cutscene (see accounts/templates/
    _role_cutscenes.html) should auto-play on the next home_view render,
    and stashes its key in the session for home_view to pop - same
    "set here, consumed on the very next page load" shape as
    force_rules_gate_on_login above, and it rides the same event (this
    account's very first login after registering, OR a regular
    subsequent login, covers both the public register_view flow and
    guest_register_view's direct login() call).

    Agent/Guest accounts get a "_create" variant exactly once - their
    first successful login ever (see CustomUser.has_completed_first_login,
    flipped True right here so every later login for that same account
    gets the "_login" variant instead). Admin/Director have no "_create"
    cutscene at all (those roles are only ever reached by promotion, not
    public self-registration) - every one of their logins is a "_login".
    """
    if user.is_guest:
        is_first_login = not user.has_completed_first_login
        cutscene_key = 'guest_create' if is_first_login else 'guest_login'
    elif user.role == CustomUser.ROLE_DIRECTOR:
        is_first_login = False
        cutscene_key = 'director_login'
    elif user.role == CustomUser.ROLE_ADMIN:
        is_first_login = False
        cutscene_key = 'admin_login'
    else:
        is_first_login = not user.has_completed_first_login
        cutscene_key = 'agent_create' if is_first_login else 'agent_login'

    if is_first_login:
        user.has_completed_first_login = True
        user.save(update_fields=['has_completed_first_login'])

    request.session['role_cutscene'] = cutscene_key
