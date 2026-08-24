from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # Home: send visitors straight to the profile (if logged in) or login page.
    path('', views.profile_view, name='home'),

    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/<str:username>/', views.profile_view, name='user_profile'),
]
