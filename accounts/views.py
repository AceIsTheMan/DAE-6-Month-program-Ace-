from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfileEditForm, RegisterForm
from .models import CustomUser


def register_view(request):
    """
    Handle new agent registration.
    GET  -> show the blank form.
    POST -> validate it; on success, create the account, log the user in
            immediately, and send them to their new profile. On failure,
            re-render the form with field-by-field error messages.
    """
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('profile')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile_view(request, username=None):
    """
    Display a user's profile. Defaults to the logged-in user's profile.
    """
    if username:
        user = get_object_or_404(CustomUser, username=username)
    else:
        user = request.user

    return render(request, 'profile.html', {'profile_user': user})


@login_required
def profile_edit_view(request):
    """
    Let the logged-in user update their own bio / profile picture.
    """
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileEditForm(instance=request.user)

    return render(request, 'profile_edit.html', {'form': form})
