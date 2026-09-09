from datetime import timedelta

from django import forms
from django.db.models import Q

from accounts.models import CustomUser
from forum.sanitize import sanitize_post_html

from .models import Message, ModerationAction, Report, UserRelationship

MAX_MEDIA_BYTES = 25 * 1024 * 1024  # 25MB - same cap as forum.forms.PostForm
MAX_BODY_LEN = 800
MAX_REPORT_LEN = 1500
GROUP_MAX_MEMBERS = 10  # host + up to 9 invitees
REPORT_LIMIT = 3
REPORT_COOLDOWN_HOURS = 48

# Duration units accepted per ModerationAction kind - Mute is fine-grained
# (minutes up to months), Ban is coarse (weeks/months/years); Perm Ban
# takes no duration at all. Approximated as fixed day-counts (a "month"
# is 30 days, a "year" 365) rather than calendar-accurate - good enough
# for a moderation cooldown, and avoids adding a dateutil dependency for
# calendar math the project has never needed before.
MUTE_UNITS = {'minutes': timedelta(minutes=1), 'days': timedelta(days=1), 'weeks': timedelta(weeks=1), 'months': timedelta(days=30)}
BAN_UNITS = {'weeks': timedelta(weeks=1), 'months': timedelta(days=30), 'years': timedelta(days=365)}
MAX_MODERATION_REASON_LEN = 1500


def _is_blocked_pair(user_a, user_b):
    """True if either account has blocked the other - see
    mail.models.UserRelationship's docstring on why a block is treated as
    bidirectional at this layer even though the row only records one
    direction. A block involving a moderator (Admin/Director) is always
    inert, on either side - "the block button is futile" against/from a
    moderator, so their reach can never be walled off."""
    if user_a.is_moderator or user_b.is_moderator:
        return False
    return UserRelationship.objects.filter(
        kind=UserRelationship.BLOCK
    ).filter(
        Q(from_user=user_a, to_user=user_b) | Q(from_user=user_b, to_user=user_a)
    ).exists()


class MessageComposeForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body', 'media', 'gif_url']
        widgets = {
            'body': forms.Textarea(attrs={
                'class': 'mail-compose-body',
                'placeholder': 'Write a message...',
                'rows': 3,
                'maxlength': MAX_BODY_LEN,
            }),
            # One attachment per message, same as forum.forms.PostForm's
            # `media` field - sending several images means several
            # messages, not a multi-file picker.
            'media': forms.ClearableFileInput(attrs={'accept': 'image/*,video/*'}),
            'gif_url': forms.HiddenInput(),
        }

    def clean_body(self):
        raw = self.cleaned_data.get('body', '')
        if len(raw) > MAX_BODY_LEN:
            raise forms.ValidationError(f'Messages are capped at {MAX_BODY_LEN} characters.')
        return sanitize_post_html(raw, apply_markers=False)

    def clean_media(self):
        media = self.cleaned_data.get('media')
        if media and getattr(media, 'size', 0) > MAX_MEDIA_BYTES:
            raise forms.ValidationError('That file is too large (25MB max).')
        return media

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(f) for f in ('body', 'media', 'gif_url')):
            raise forms.ValidationError('A message needs at least some text, an image/video, or a GIF.')
        return cleaned


class _RecipientPickerForm(forms.Form):
    """Shared base for any form fed by the recipient-picker UI (New
    Group, Directive send, Forum Share) - a comma-separated list of
    usernames, resolved and validated into real CustomUser objects."""
    usernames = forms.CharField(widget=forms.HiddenInput())

    #: Subclasses that need to allow the block-filter to be skipped (a
    #: Director sending a Directive must always be able to reach anyone)
    #: set this to False.
    enforce_block_filter = True
    #: Subclasses set a concrete cap; None means no upper bound.
    max_recipients = None

    def __init__(self, *args, sender=None, **kwargs):
        self.sender = sender
        super().__init__(*args, **kwargs)

    def clean_usernames(self):
        raw = self.cleaned_data.get('usernames', '')
        names = [n.strip() for n in raw.split(',') if n.strip()]
        if not names:
            raise forms.ValidationError('Pick at least one recipient.')
        users = list(CustomUser.objects.filter(username__in=names))
        found_names = {u.username for u in users}
        missing = set(names) - found_names
        if missing:
            raise forms.ValidationError(f'Unknown username(s): {", ".join(sorted(missing))}.')
        if any(u.is_guest for u in users):
            raise forms.ValidationError('Guest accounts cannot be messaged or added to Social.')
        if self.enforce_block_filter and self.sender is not None:
            blocked = [u.username for u in users if _is_blocked_pair(self.sender, u)]
            if blocked:
                raise forms.ValidationError(f'Blocked: {", ".join(blocked)}.')
        if self.max_recipients is not None and len(users) > self.max_recipients:
            raise forms.ValidationError(f'Pick at most {self.max_recipients} recipients.')
        return users


class GroupCreateForm(_RecipientPickerForm):
    """Creates a Social group Conversation - host plus up to 9 invitees,
    10 total (see mail.models.Conversation's docstring on the cap)."""
    title = forms.CharField(max_length=60, required=False)
    max_recipients = GROUP_MAX_MEMBERS - 1


class DirectiveForm(_RecipientPickerForm):
    """Sends a Directive - Director-only (enforced in the view, not
    here), no upper cap on recipient count."""
    enforce_block_filter = False
    body = forms.CharField(widget=forms.Textarea(attrs={'maxlength': MAX_BODY_LEN, 'rows': 4}))

    def clean_body(self):
        raw = self.cleaned_data.get('body', '')
        if not raw.strip():
            raise forms.ValidationError('A Directive needs a message.')
        if len(raw) > MAX_BODY_LEN:
            raise forms.ValidationError(f'Directives are capped at {MAX_BODY_LEN} characters.')
        return sanitize_post_html(raw, apply_markers=True)


class ForumShareForm(_RecipientPickerForm):
    """Shares a forum Post into one or more Social DMs - see
    mail.views.mail_forum_share."""
    max_recipients = None


class UpdateForm(forms.Form):
    """Broadcasts an Update to every current non-guest account - see
    mail.views.mail_update_new. Unlike Directive, there's no recipient
    picker: "Updates are announced updates the Director has sent
    personally" reads as a broadcast, not a targeted send."""
    body = forms.CharField(widget=forms.Textarea(attrs={'maxlength': MAX_BODY_LEN, 'rows': 4}))

    def clean_body(self):
        raw = self.cleaned_data.get('body', '')
        if not raw.strip():
            raise forms.ValidationError('An Update needs a message.')
        if len(raw) > MAX_BODY_LEN:
            raise forms.ValidationError(f'Updates are capped at {MAX_BODY_LEN} characters.')
        return sanitize_post_html(raw, apply_markers=True)


class ReportForm(forms.ModelForm):
    """Reporter and target (reported_user/reported_message) are set by
    the view from resolved context, never from raw client input - see
    mail.models.Report's docstring on why. Rendered on its own full page
    (mail/templates/mail/report_new.html), not a modal - see
    mail.views.mail_report_new."""
    class Meta:
        model = Report
        fields = ['category', 'reason', 'media']
        widgets = {
            'category': forms.Select(),
            'reason': forms.Textarea(attrs={
                'maxlength': MAX_REPORT_LEN, 'rows': 6, 'placeholder': 'What happened?',
            }),
            'media': forms.ClearableFileInput(attrs={'accept': 'image/*,video/*'}),
        }

    def clean_reason(self):
        raw = self.cleaned_data.get('reason', '')
        if not raw.strip():
            raise forms.ValidationError('A report needs a reason.')
        if len(raw) > MAX_REPORT_LEN:
            raise forms.ValidationError(f'Reports are capped at {MAX_REPORT_LEN} characters.')
        return sanitize_post_html(raw, apply_markers=False)

    def clean_media(self):
        media = self.cleaned_data.get('media')
        if media and getattr(media, 'size', 0) > MAX_MEDIA_BYTES:
            raise forms.ValidationError('That file is too large (25MB max).')
        return media


class ModerationActionForm(forms.Form):
    """Backs mail.views.mail_moderation_new - a moderator muting/banning
    an account. `kind` decides which duration units are even valid (see
    MUTE_UNITS/BAN_UNITS) - Perm Ban ignores duration entirely, it's
    indefinite until lifted by hand (see mail.views.mail_moderation_lift).
    A reason is required no matter which kind this is."""
    kind = forms.ChoiceField(choices=ModerationAction.KIND_CHOICES)
    duration_amount = forms.IntegerField(required=False, min_value=1)
    duration_unit = forms.CharField(required=False)
    reason = forms.CharField(widget=forms.Textarea(attrs={'maxlength': MAX_MODERATION_REASON_LEN, 'rows': 5}))

    def clean_reason(self):
        raw = self.cleaned_data.get('reason', '')
        if not raw.strip():
            raise forms.ValidationError('A reason is required for every moderation action.')
        if len(raw) > MAX_MODERATION_REASON_LEN:
            raise forms.ValidationError(f'Reasons are capped at {MAX_MODERATION_REASON_LEN} characters.')
        return sanitize_post_html(raw, apply_markers=False)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('kind')
        if kind == ModerationAction.PERM_BAN:
            cleaned['duration'] = None
            return cleaned

        units = MUTE_UNITS if kind == ModerationAction.MUTE else BAN_UNITS
        amount = cleaned.get('duration_amount')
        unit = cleaned.get('duration_unit')
        if not amount:
            raise forms.ValidationError('Pick a duration.')
        if unit not in units:
            raise forms.ValidationError(f'Duration must be one of: {", ".join(units)}.')
        cleaned['duration'] = units[unit] * amount
        return cleaned
