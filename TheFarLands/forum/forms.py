from django import forms

from .models import Post
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
            # The real editing surface is the contenteditable toolbar div
            # in the template - this textarea just carries its sanitized
            # HTML on submit (see the script in templates/forum/index.html).
            'body': forms.Textarea(attrs={'class': 'hidden-body-field'}),
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
