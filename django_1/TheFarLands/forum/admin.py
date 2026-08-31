from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'created_at', 'has_image', 'has_video', 'has_link')
    list_filter = ('author',)
    readonly_fields = ('created_at',)

    @admin.display(boolean=True)
    def has_image(self, obj):
        return bool(obj.image)

    @admin.display(boolean=True)
    def has_video(self, obj):
        return bool(obj.video_url)

    @admin.display(boolean=True)
    def has_link(self, obj):
        return bool(obj.link_url)
