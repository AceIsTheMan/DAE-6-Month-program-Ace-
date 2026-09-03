from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, GuestArchive


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('The Far Lands profile', {'fields': ('bio', 'profile_picture', 'rank')}),
    )
    list_display = ('username', 'email', 'rank', 'is_staff')


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(GuestArchive)
class GuestArchiveAdmin(admin.ModelAdmin):
    """Read-only history of expired guest ("Hacker") accounts - see
    accounts.middleware.GuestExpiryMiddleware. Nothing here should ever
    be edited after the fact, so every field is locked to read-only."""
    list_display = ('username', 'alias', 'rank', 'date_joined', 'archived_at', 'reaction_count')
    search_fields = ('username', 'alias')
    ordering = ('-archived_at',)
    readonly_fields = [f.name for f in GuestArchive._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
