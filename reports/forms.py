from django import forms
from .models import Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        labels = {"details": "What happened?"}
        help_texts = {"details": "Describe the concern and include relevant context. Up to 5,000 characters."}
        widgets = {"details": forms.Textarea(attrs={"rows": 6, "maxlength": 5000})}


class ReportReviewForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["status", "review_notes"]
        labels = {"review_notes": "Investigation notes"}
        help_texts = {"review_notes": "Visible only to administrators. Explain your findings and any action taken."}
        widgets = {"review_notes": forms.Textarea(attrs={"rows": 6, "maxlength": 10000})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == Report.Status.RESOLVED and not cleaned.get("review_notes"):
            self.add_error("review_notes", "Add investigation notes before resolving this report.")
        return cleaned
