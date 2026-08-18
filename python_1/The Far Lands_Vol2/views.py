from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import CustomUser

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
