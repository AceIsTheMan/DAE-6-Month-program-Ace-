from django.urls import path

from . import views

urlpatterns = [
    path('', views.mail_inbox, name='mail_inbox'),
    path('sent/', views.mail_sent, name='mail_sent'),
    path('updates/', views.mail_updates, name='mail_updates'),
    path('update/new/', views.mail_update_new, name='mail_update_new'),
    path('directives/', views.mail_directives, name='mail_directives'),
    path('directive/new/', views.mail_directive_new, name='mail_directive_new'),
    path('social/', views.mail_social, name='mail_social'),
    path('social/group/new/', views.mail_group_new, name='mail_group_new'),
    path('social/dm/<str:username>/', views.mail_social_dm_start, name='mail_social_dm_start'),
    path('social/<int:conversation_id>/', views.mail_social_thread, name='mail_social_thread'),
    path('friends/', views.mail_friends, name='mail_friends'),
    path('reports/', views.mail_reports, name='mail_reports'),
    path('reports/history/', views.mail_report_history, name='mail_report_history'),
    path('reports/<int:report_id>/resolve/', views.mail_report_resolve, name='mail_report_resolve'),
    path('report/new/', views.mail_report_new, name='mail_report_new'),
    path('recipients/search/', views.mail_recipient_search, name='mail_recipient_search'),
    path('share/post/<int:post_id>/', views.mail_forum_share, name='mail_forum_share'),
    path('gif-search/', views.mail_gif_search, name='mail_gif_search'),
    path('relationship/<str:username>/friend/', views.mail_relationship_friend, name='mail_relationship_friend'),
    path('relationship/<str:username>/mute/', views.mail_relationship_mute, name='mail_relationship_mute'),
    path('relationship/<str:username>/block/', views.mail_relationship_block, name='mail_relationship_block'),
]
