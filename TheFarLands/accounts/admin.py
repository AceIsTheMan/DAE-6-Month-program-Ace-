from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, GuestArchive, PurchaseLog, TokenGrantLog, TokenTransaction


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


@admin.register(TokenTransaction)
class TokenTransactionAdmin(admin.ModelAdmin):
    """Read-only view of the per-user Cipher Token ledger shown on the
    Mail app's Cipher Tokens tab (mail.views.mail_tokens) - locked for
    the same reason as TokenGrantLog below: a ledger that can be edited
    after the fact isn't a ledger."""
    list_display = ('user', 'kind', 'amount', 'balance_after', 'created_at')
    list_filter = ('kind',)
    search_fields = ('user__username', 'note')
    ordering = ('-created_at',)
    readonly_fields = [f.name for f in TokenTransaction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PurchaseLog)
class PurchaseLogAdmin(admin.ModelAdmin):
    """Read-only record of real (fake-money) Store spending - backs the
    Top Donators leaderboard on the Socials & Support page."""
    list_display = ('user', 'label', 'quantity', 'amount_cents', 'created_at')
    search_fields = ('user__username', 'label')
    ordering = ('-created_at',)
    readonly_fields = [f.name for f in PurchaseLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TokenGrantLog)
class TokenGrantLogAdmin(admin.ModelAdmin):
    """Read-only audit trail for the "!Token_<amount>" cheat code (see
    accounts.views.director_grant_tokens) - every grant is permanent
    history, nothing here should ever be edited after the fact."""
    list_display = ('director', 'amount', 'new_balance', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = [f.name for f in TokenGrantLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
