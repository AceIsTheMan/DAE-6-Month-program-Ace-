from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import GuestRegisterForm, ProfileEditForm, RegisterForm
from .models import CustomUser


def home_view(request):
    """
    Public landing page - The Far Lands main site (the old TFL_index.html,
    now served through Django so login state is real instead of guessed).
    """
    return render(request, 'home.html')


def register_view(request):
    """
    Handle new agent registration.
    GET  -> show the blank form.
    POST -> validate it; on success, create the account, log the user in
            immediately, and send them to the home page (not straight into
            an edit form - they can go edit their profile whenever they
            want from there). On failure, re-render the form with
            field-by-field error messages.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


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
