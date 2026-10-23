from django import forms

from .models import Message


class MessageForm(forms.ModelForm):
    body = forms.CharField(
        label="Message",
        max_length=2000,
        strip=True,
        help_text="Up to 2,000 characters.",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Write a message…",
            }
        ),
    )

    class Meta:
        model = Message
        fields = ["body"]


class CandidateEmailForm(forms.Form):
    subject = forms.CharField(max_length=200, strip=True)
    body = forms.CharField(
        label="Email message",
        max_length=10000,
        strip=True,
        help_text="Up to 10,000 characters. Sent as plain text.",
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        if "\r" in subject or "\n" in subject:
            raise forms.ValidationError("Use a single line for the subject.")
        return subject
