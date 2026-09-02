from django.urls import path

from . import views

urlpatterns = [
    path('', views.forum_index_view, name='forum'),
    path('react/<int:post_id>/', views.forum_react_view, name='forum_react'),
    path('delete/<int:post_id>/', views.forum_delete_post_view, name='forum_delete_post'),
]
