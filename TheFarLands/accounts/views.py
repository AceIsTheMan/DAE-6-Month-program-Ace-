from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .forms import GuestRegisterForm, ProfileEditForm, RegisterForm
from .models import CustomUser


def home_view(request):
    """
    Public landing page - The Far Lands main site (the old TFL_index.html,
    now served through Django so login state is real instead of guessed).

    force_rules_gate is a one-shot flag set by accounts.signals whenever
    someone just logged in (regular or guest) - it tells the template/JS to
    show the "BE ADVISED" rules popup again even if this browser tab
    already dismissed it earlier as an anonymous visitor. It's popped (read
    AND removed) here so it only fires on the page load right after login,
    not on every later visit to home in the same session.
    """
    force_rules_gate = request.session.pop('force_rules_gate', False)
    return render(request, 'home.html', {'force_rules_gate': force_rules_gate})


def _send_verification_email(request, user):
    """
    Emails a one-time verification link to a newly-registered (non-guest)
    account. Uses Django's own password-reset token machinery
    (default_token_generator) purely because it already does exactly what
    we need here too: a signed, single-use-ish token tied to this specific
    user that can't be guessed or reused once the account state it was
    built from (password / last_login) changes.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(
        reverse('verify_email', args=[uidb64, token])
    )
    send_mail(
        subject='Verify your Far Lands account',
        message=(
            f'Hey {user.username},\n\n'
            f'Click the link below to verify your email and activate your '
            f'Far Lands account:\n\n{verify_url}\n\n'
            f"If you didn't sign up for this, you can just ignore this email."
        ),
        from_email=None,  # falls back to settings.DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
    )


def register_view(request):
    """
    Handle new agent registration.
    GET  -> show the blank form.
    POST -> validate it; on success, create the account (email_verified=False
            until they click the link - see RegisterForm.save()), email them
            a verification link, and show a "check your email" page. They
            aren't logged in yet - that happens after they click the link
            and then log in normally. On failure, re-render the form with
            field-by-field error messages.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Verification feature is toggled off for now (see
            # settings.EMAIL_VERIFICATION_ENABLED) - RegisterForm.save()
            # already auto-verified the account, so there's no link to
            # send; skip straight to "you're set, go log in" instead of
            # "check your email".
            if settings.EMAIL_VERIFICATION_ENABLED:
                _send_verification_email(request, user)
            return render(request, 'registration/check_email.html', {
                'email': user.email,
                'is_console_backend': settings.EMAIL_BACKEND.endswith('console.EmailBackend'),
                'verification_enabled': settings.EMAIL_VERIFICATION_ENABLED,
            })
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


def verify_email_view(request, uidb64, token):
    """
    Handles the link from _send_verification_email(). Marks the account
    email_verified=True (NOT is_active - see CustomUser.email_verified's
    docstring for why those had to be separate flags) if the uid decodes to
    a real user and the token checks out; otherwise shows a "link
    invalid/expired" message instead of erroring. Doesn't log the user in
    itself - they still go through /login/ normally afterward, same as
    everyone else.
    """
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    verified = False
    if user is not None and default_token_generator.check_token(user, token):
        user.email_verified = True
        user.save()
        verified = True

    return render(request, 'registration/verify_result.html', {'verified': verified})


def guest_register_view(request):
    """
    Handle temporary "Hacker" guest registration - just a codename and
    password, no email. Same flow as a normal registration otherwise (log
    in immediately, land on home): the account is simply marked
    is_guest=True, which is what limits it everywhere else - no profile
    picture, shown as HACKER instead of AGENT on their profile, and
    automatically deleted after CustomUser.GUEST_TRIAL_DAYS by
    GuestExpiryMiddleware.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = GuestRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_guest = True
            user.save()
            login(request, user)
            return redirect('home')
    else:
        form = GuestRegisterForm()

    return render(request, 'registration/guest_register.html', {'form': form})


@login_required
def profile_view(request, username=None):
    """
    Display a user's profile. Defaults to the logged-in user's profile.

    When you're looking at your OWN profile, this also handles saving
    edits (bio / profile picture) right on the same page - no separate
    "stuck on an edit screen" step.
    """
    if username:
        user = get_object_or_404(CustomUser, username=username)
    else:
        user = request.user

    is_own_profile = (user == request.user)
    edit_form = None

    if is_own_profile:
        if request.method == 'POST':
            edit_form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
            if edit_form.is_valid():
                edit_form.save()
                return redirect('profile')
        else:
            edit_form = ProfileEditForm(instance=request.user)

    return render(request, 'profile.html', {
        'profile_user': user,
        'edit_form': edit_form,
    })


@login_required
def profile_edit_view(request):
    """
    Deprecated standalone edit page - editing now happens inline on
    /profile/ itself. Kept as a redirect so the old URL/bookmark still
    goes somewhere sensible instead of 404ing.
    """
    return redirect('profile')
