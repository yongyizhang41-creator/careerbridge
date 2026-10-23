from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import (
    Education,
    JobSeekerProfile,
    ProfessionalLink,
    Project,
    User,
    WorkExperience,
    SavedSearch,
)


class RegistrationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[
            (User.Role.JOB_SEEKER, "Job Seeker"),
            (User.Role.RECRUITER, "Recruiter"),
        ]
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")


class JobSeekerProfileForm(forms.ModelForm):
    class Meta:
        model = JobSeekerProfile
        fields = ("headline", "skills", "location", "lat", "lng", "recruiter_visible")
        labels = {
            "recruiter_visible": "Allow recruiter discovery",
        }
        widgets = {
            "headline": forms.TextInput(
                attrs={"placeholder": "e.g. Aspiring software engineer"}
            ),
            "skills": forms.TextInput(
                attrs={"placeholder": "e.g. Python, Django, SQL"}
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "e.g. Atlanta, GA"}
            ),
            # The pin is placed on the map; these inputs carry its coordinates.
            "lat": forms.HiddenInput(),
            "lng": forms.HiddenInput(),
        }

    def clean(self):
        cleaned = super().clean()
        lat, lng = cleaned.get("lat"), cleaned.get("lng")
        if (lat is None) != (lng is None):
            self.add_error("lat", "Pin your location on the map, or clear the pin.")
        elif lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            self.add_error("lat", "That pin is off the map. Clear it and try again.")
        return cleaned


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = (
            "institution",
            "degree",
            "field_of_study",
            "start_date",
            "end_date",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = (
            "company",
            "title",
            "description",
            "start_date",
            "end_date",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ProfessionalLinkForm(forms.ModelForm):
    class Meta:
        model = ProfessionalLink
        fields = ("label", "url")
        widgets = {
            "label": forms.TextInput(
                attrs={"placeholder": "e.g. LinkedIn or GitHub"}
            ),
            "url": forms.URLInput(
                attrs={"placeholder": "https://example.com"}
            ),
        }

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("title", "description", "url")
        labels = {"url": "Link (optional)"}
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "e.g. Campus food delivery app"}
            ),
            "description": forms.Textarea(
                attrs={"rows": 4, "placeholder": "What you built and the tools you used"}
            ),
            "url": forms.URLInput(
                attrs={"placeholder": "https://github.com/you/project"}
            ),
        }


class CandidateSearchForm(forms.Form):
    skills = forms.CharField(
        required=False,
        help_text="Comma-separated; candidates must have every skill, e.g. Python, SQL",
    )
    location = forms.CharField(required=False)
    project = forms.CharField(
        required=False,
        label="Project keyword",
        help_text="Matches project titles and descriptions, e.g. React or machine learning",
    )


class SavedSearchForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ("name", "skills", "location", "project")

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(f) for f in ("skills", "location", "project")):
            raise forms.ValidationError("Add at least one filter before saving a search.")
        return cleaned


class ManagedUserForm(forms.ModelForm):
    """Only expose account fields that this website is allowed to change."""

    class Meta:
        model = User
        fields = ("username", "email", "role", "is_active")

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        protected = self.instance.pk == actor.pk or (
            self.instance.is_superuser and not actor.is_superuser
        )
        if protected:
            for field in self.fields.values():
                field.disabled = True


class ManagedUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role", "is_active")


class ManagedUserRowForm(ManagedUserForm):
    class Meta(ManagedUserForm.Meta):
        fields = ("role", "is_active")


class ManagedUserFormSet(forms.BaseModelFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        expected = set(self.get_queryset().values_list("pk", flat=True))
        submitted = [form.instance.pk for form in self.forms]
        if len(submitted) != len(expected) or set(submitted) != expected:
            raise forms.ValidationError("The user list changed. Reload the page and try again.")
