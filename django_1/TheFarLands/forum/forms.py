from django import forms

from .models import Post
from .sanitize import sanitize_post_html


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['body', 'image', 'video_url', 'link_url', 'link_label']
        widgets = {
            # The real editing surface is the contenteditable toolbar div
            # in the template - this textarea just carries its sanitized
            # HTML on submit (see the script in templates/forum/index.html).
            'body': forms.Textarea(attrs={'class': 'hidden-body-field'}),
            'video_url': forms.URLInput(attrs={'placeholder': 'https://youtube.com/... or a direct .mp4 link'}),
            'link_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'link_label': forms.TextInput(attrs={'placeholder': 'Optional link text'}),
        }

    def clean_body(self):
        return sanitize_post_html(self.cleaned_data.get('body', ''))

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(f) for f in ('body', 'image', 'video_url', 'link_url')):
            raise forms.ValidationError('A post needs at least some text, an image, a video, or a link.')
        return cleaned
