from django.contrib import admin

from .models import Comment, Post, PostReaction


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'created_at', 'edited_at', 'has_media', 'has_link', 'like_count', 'dislike_count')
    list_filter = ('author',)
    readonly_fields = ('created_at',)

    @admin.display(boolean=True)
    def has_media(self, obj):
        return bool(obj.media)

    @admin.display(boolean=True)
    def has_link(self, obj):
        return bool(obj.link_url)


@admin.register(PostReaction)
class PostReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'user', 'value', 'created_at')
    list_filter = ('value',)
    readonly_fields = ('created_at',)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'author', 'created_at')
    list_filter = ('author',)
    readonly_fields = ('created_at',)
