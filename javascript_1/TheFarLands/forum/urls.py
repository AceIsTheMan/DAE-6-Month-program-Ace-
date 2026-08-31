from django.urls import path

from . import views

urlpatterns = [
    path('', views.forum_index_view, name='forum'),
]
