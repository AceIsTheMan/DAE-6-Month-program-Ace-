from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('The Far Lands profile', {'fields': ('bio', 'profile_picture', 'rank')}),
    )
    list_display = ('username', 'email', 'rank', 'is_staff')


admin.site.register(CustomUser, CustomUserAdmin)
