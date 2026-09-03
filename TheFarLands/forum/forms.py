from django import forms

from .models import Comment, Post
from .sanitize import sanitize_post_html

MAX_MEDIA_BYTES = 25 * 1024 * 1024  # 25MB - images and short video clips only


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['body', 'media', 'link_url', 'link_label']
        labels = {
            # Field is named `media` (image or video) but stays "Image" in
            # the UI - see forum.models.Post.media.
            'media': 'Image',
        }
        widgets = {
            # Plain textarea - the poster types the formatting markers
            # directly (see forum.sanitize), no rich-text editing surface.
            'body': forms.Textarea(attrs={
                'class': 'composer-body',
                'placeholder': 'Write a transmission... **bold** __underline__ ~~crossed~~ ||redacted|| ==highlight==',
                'rows': 5,
            }),
            'media': forms.ClearableFileInput(attrs={'accept': 'image/*,video/*'}),
            'link_url': forms.URLInput(attrs={'placeholder': 'https://... (can point to footage)'}),
            'link_label': forms.TextInput(attrs={'placeholder': 'Optional link text'}),
        }
        help_texts = {
            'media': 'Upload an image or a short video from your computer.',
        }

    def clean_body(self):
        return sanitize_post_html(self.cleaned_data.get('body', ''))

    def clean_media(self):
        media = self.cleaned_data.get('media')
        if media and getattr(media, 'size', 0) > MAX_MEDIA_BYTES:
            raise forms.ValidationError('That file is too large (25MB max).')
        return media

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(f) for f in ('body', 'media', 'link_url')):
            raise forms.ValidationError('A post needs at least some text, an image/video, or a link.')
        return cleaned


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'class': 'composer-body comment-input',
                'placeholder': 'Write a comment... **bold** __underline__ ~~crossed~~ ||redacted|| ==highlight==',
                'rows': 2,
                'maxlength': 2000,
            }),
        }

    def clean_body(self):
        raw = self.cleaned_data.get('body', '')
        if not raw.strip():
            raise forms.ValidationError('Comment cannot be empty.')
        return sanitize_post_html(raw)
