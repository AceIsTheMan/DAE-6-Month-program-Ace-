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

    path('settings/', views.settings_view, name='settings_page'),
    path('settings/logs/<str:kind>/<int:obj_id>/resend/', views.chat_log_resend, name='chat_log_resend'),
    path('settings/logs/<str:kind>/<int:obj_id>/purge/', views.chat_log_purge, name='chat_log_purge'),
    path('settings/notifications/toggle/', views.settings_toggle_notifications, name='settings_toggle_notifications'),
    path('settings/cutscenes/update/', views.settings_update_cutscene_mode, name='settings_update_cutscene_mode'),
    path('settings/cutscenes/c1/toggle/', views.settings_toggle_secret_cutscene, name='settings_toggle_secret_cutscene'),
    path('settings/director/grant-tokens/', views.director_grant_tokens, name='director_grant_tokens'),
    path('store/purchase/', views.store_purchase, name='store_purchase'),
    path('store/gift/', views.store_gift, name='store_gift'),
    path('status/toggle/', views.toggle_status, name='toggle_status'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/<str:username>/', views.profile_view, name='user_profile'),
]
