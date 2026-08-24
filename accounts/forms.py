from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser


class RegisterForm(UserCreationForm):
    """
    Registration form for The Far Lands.

    Extends Django's battle-tested UserCreationForm (which already handles
    password confirmation matching + password strength validation) and adds
    an email field plus the site's "agree to the rules" checkbox.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    agree_to_rules = forms.BooleanField(
        required=True,
        label='I have read and understood the rules above.',
        error_messages={'required': 'You must agree to the rules to register.'},
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('bio', 'profile_picture')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'maxlength': 500}),
        }
