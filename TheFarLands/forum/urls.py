from django.urls import path

from . import views

urlpatterns = [
    path('', views.forum_index_view, name='forum'),
    path('react/<int:post_id>/', views.forum_react_view, name='forum_react'),
    path('delete/<int:post_id>/', views.forum_delete_post_view, name='forum_delete_post'),
    path('edit/<int:post_id>/', views.forum_edit_post_view, name='forum_edit_post'),
    path('<int:post_id>/comments/', views.forum_comments_view, name='forum_comments'),
    path('<int:post_id>/comments/add/', views.forum_add_comment_view, name='forum_add_comment'),
]
