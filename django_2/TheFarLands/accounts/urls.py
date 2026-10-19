from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import EmailVerifiedLoginForm

urlpatterns = [
    # Home: the real, public Far Lands landing page (was TFL_index.html).
    path('', views.home_view, name='home'),

    path('register/', views.register_view, name='register'),
    path('guest/', views.guest_register_view, name='guest_register'),
    path(
        'verify/<uidb64>/<token>/',
        views.verify_email_view,
        name='verify_email',
    ),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=EmailVerifiedLoginForm,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/<str:username>/', views.profile_view, name='user_profile'),
]
