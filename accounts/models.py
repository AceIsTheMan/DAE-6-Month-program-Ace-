from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Custom User Model for The Far Lands Project.
    Inherits from AbstractUser to keep default auth features.
    """
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    rank = models.CharField(max_length=50, default='Newbie')
    alias = models.CharField(max_length=12, blank=True)

    def __str__(self):
        return self.username
