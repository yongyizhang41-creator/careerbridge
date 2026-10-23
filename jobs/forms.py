from django import forms
from .models import Application, Job


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["note"]
        labels = {"note": "Personalized note (optional)"}
        help_texts = {"note": "Tell the hiring team why this role fits you. Up to 2,000 characters."}
        widgets = {"note": forms.Textarea(attrs={"rows": 4, "maxlength": 2000})}


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status"]


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "title",
            "company",
            "description",
            "address",
            "lat",
            "lng",
            "salary_min",
            "salary_max",
            "remote_type",
            "visa_sponsorship",
            "skills",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            # The office pin is chosen on the map; these inputs carry its coordinates.
            "lat": forms.HiddenInput(),
            "lng": forms.HiddenInput(),
        }

    def _clean_coordinate(self, name, limit, label):
        value = self.cleaned_data.get(name)
        if value is None:
            return None
        if not -limit <= value <= limit:
            raise forms.ValidationError(f"{label} must be between -{limit} and {limit}.")
        return round(value, 6)

    def clean_lat(self):
        return self._clean_coordinate("lat", 90, "Latitude")

    def clean_lng(self):
        return self._clean_coordinate("lng", 180, "Longitude")

    def clean(self):
        cleaned = super().clean()
        lo = cleaned.get("salary_min")
        hi = cleaned.get("salary_max")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("salary_max", "Max salary must be at least min salary.")
        if not self.has_error("lat") and not self.has_error("lng"):
            if (cleaned.get("lat") is None) != (cleaned.get("lng") is None):
                self.add_error("lat", "Pin the office location on the map, or clear the pin.")
        return cleaned
class JobSearchForm(forms.Form):
    title = forms.CharField(required=False)
    skills = forms.CharField(
        required=False,
        help_text="Comma-separated, e.g. Python, SQL",
    )
    location = forms.CharField(required=False)
    salary_min = forms.IntegerField(required=False, min_value=0, label="Min salary")
    salary_max = forms.IntegerField(required=False, min_value=0, label="Max salary")
    remote_type = forms.ChoiceField(
        required=False,
        choices=[("", "Any")] + list(Job.RemoteType.choices),
        label="Work type",
    )
    visa_sponsorship = forms.BooleanField(required=False, label="Visa sponsorship only")

    def clean(self):
        cleaned = super().clean()
        lo = cleaned.get("salary_min")
        hi = cleaned.get("salary_max")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("salary_max", "Max salary must be at least min salary.")
        return cleaned


class CommuteRadiusForm(forms.Form):
    """The distance choices on the job map; saving one makes it the commute radius."""

    CHOICES = [
        ("", "Any distance"),
        (5, "Within 5 miles"),
        (10, "Within 10 miles"),
        (25, "Within 25 miles"),
        (50, "Within 50 miles"),
    ]

    radius = forms.TypedChoiceField(
        choices=CHOICES,
        coerce=int,
        required=False,
        empty_value=None,
        label="Distance from me",
        widget=forms.Select(attrs={"class": "radius-select", "data-radius": ""}),
    )
