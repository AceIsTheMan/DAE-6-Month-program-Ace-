from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import CustomUser


class RegisterForm(UserCreationForm):
    """
    Registration form for The Far Lands.

    Extends Django's battle-tested UserCreationForm (which already handles
    password confirmation matching + password strength validation) and adds
    an email field plus the site's "agree to the rules" checkbox.

    Accounts created here start with email_verified=False until the
    person clicks the verification link emailed to them - see
    accounts.views.register_view / verify_email_view. Guest ("Hacker")
    accounts skip all of this entirely; see GuestRegisterForm below.
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
        user.email_verified = False
        if commit:
            user.save()
        return user


class EmailVerifiedLoginForm(AuthenticationForm):
    """
    The site's normal login form, but blocks accounts that haven't
    verified their email yet, with a message that actually explains why.

    Deliberately checks email_verified rather than is_active: Django's own
    authenticate() already refuses is_active=False users before a login
    form ever gets a chance to run custom checks or show a custom message,
    which is why this needed its own separate field instead. Guest
    ("Hacker") accounts always have email_verified=True, so they're never
    affected.
    """

    def confirm_login_allowed(self, user):
        if not user.email_verified:
            raise forms.ValidationError(
                "You need to verify your email before logging in - check "
                "the inbox (or your terminal, in dev/test mode) for the "
                "link we sent when you registered.",
                code='email_not_verified',
            )


class GuestRegisterForm(UserCreationForm):
    """
    Minimal registration for temporary "Hacker" guest accounts: just a
    codename and password, no email. Guest accounts get a short trial
    (see CustomUser.GUEST_TRIAL_DAYS and accounts.middleware
    .GuestExpiryMiddleware, which deletes them once it's up) and can never
    set a profile picture (see ProfileEditForm below) - is_guest itself
    gets set by the view after this form saves, since it isn't a field a
    user should be able to fill in themselves.
    """
    agree_to_rules = forms.BooleanField(
        required=True,
        label='I have read and understood the rules above.',
        error_messages={'required': 'You must agree to the rules to register.'},
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username',)


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('alias', 'bio', 'profile_picture')
        widgets = {
            'alias': forms.TextInput(attrs={'maxlength': 12, 'placeholder': 'Name'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'maxlength': 500}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Guest ("Hacker") accounts can't set a profile picture - drop the
        # field entirely so this is enforced server-side, not just hidden
        # in the template (a guest POSTing the field directly would
        # otherwise still be able to set one).
        if getattr(self.instance, 'is_guest', False):
            self.fields.pop('profile_picture', None)
