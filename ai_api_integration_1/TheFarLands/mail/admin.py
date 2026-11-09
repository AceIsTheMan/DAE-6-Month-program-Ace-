from django.contrib import admin

from .models import Conversation, Message, ModerationAction, Report, UserRelationship


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'created_by', 'title', 'created_at', 'last_message_at')
    list_filter = ('category',)
    readonly_fields = ('created_at', 'last_message_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'created_at', 'has_media', 'has_gif', 'has_shared_post')
    list_filter = ('conversation__category',)
    readonly_fields = ('created_at',)

    @admin.display(boolean=True)
    def has_media(self, obj):
        return bool(obj.media)

    @admin.display(boolean=True)
    def has_gif(self, obj):
        return bool(obj.gif_url)

    @admin.display(boolean=True)
    def has_shared_post(self, obj):
        return bool(obj.shared_post_id)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    # Doubles as a zero-cost v1 moderation UI alongside the dedicated
    # mail_reports view - same role Django admin already plays for
    # accounts.GuestArchive.
    list_display = ('id', 'reporter', 'reported_user', 'reported_message', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('reporter__username', 'reported_user__username')
    readonly_fields = ('created_at',)


@admin.register(UserRelationship)
class UserRelationshipAdmin(admin.ModelAdmin):
    list_display = ('id', 'from_user', 'to_user', 'kind', 'created_at')
    list_filter = ('kind',)
    readonly_fields = ('created_at',)


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'target', 'moderator', 'created_at', 'expires_at', 'is_active_display')
    list_filter = ('kind',)
    search_fields = ('target__username', 'moderator__username')
    readonly_fields = ('created_at',)

    @admin.display(boolean=True, description='Active')
    def is_active_display(self, obj):
        return obj.is_active
