from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


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
