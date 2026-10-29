from django.urls import path
from myapp import views  # <-- Replace "myapp" with the exact name of your app folder

urlpatterns = [
    # This must link directly to your home_view function!
    path('', views.home_view, name='home'), 
]