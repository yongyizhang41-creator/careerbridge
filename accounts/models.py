from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models



class User(AbstractUser):
    class Role(models.TextChoices):
        JOB_SEEKER = "job_seeker", "Job Seeker"
        RECRUITER = "recruiter", "Recruiter"
        ADMINISTRATOR = "administrator", "Administrator"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.JOB_SEEKER,
    )

    def __str__(self):
        return self.username


class JobSeekerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_seeker_profile",
    )
    headline = models.CharField(max_length=200, blank=True)
    skills = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated, e.g. Python, Django, SQL",
    )
    location = models.CharField(max_length=255, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    commute_radius = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Preferred commute radius in miles; the job map applies it automatically.",
    )
    recruiter_visible = models.BooleanField(
        default=False,
        help_text=(
            "Allow recruiters to discover and view your profile. "
            "Recruiters whose jobs you apply to can still view it."
        ),
    )


    def __str__(self):
        return f"{self.user.username}'s profile"

    def skill_list(self):
        return [skill.strip() for skill in self.skills.split(",") if skill.strip()]


class Education(models.Model):
    profile = models.ForeignKey(
        JobSeekerProfile,
        on_delete=models.CASCADE,
        related_name="education_records",
    )
    institution = models.CharField(max_length=200)
    degree = models.CharField(max_length=200, blank=True)
    field_of_study = models.CharField(max_length=200, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.institution} — {self.profile.user.username}"


class WorkExperience(models.Model):
    profile = models.ForeignKey(
        JobSeekerProfile,
        on_delete=models.CASCADE,
        related_name="work_experiences",
    )
    company = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} at {self.company}"


class ProfessionalLink(models.Model):
    profile = models.ForeignKey(
        JobSeekerProfile,
        on_delete=models.CASCADE,
        related_name="professional_links",
    )
    label = models.CharField(max_length=100)
    url = models.URLField()

    def __str__(self):
        return f"{self.label} — {self.profile.user.username}"
    
class Project(models.Model):
    profile = models.ForeignKey(
        JobSeekerProfile,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.title} - {self.profile.user.username}"

    
class SavedSearch(models.Model):
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    name = models.CharField(max_length=100)
    skills = models.CharField(max_length=500, blank=True)
    location = models.CharField(max_length=255, blank=True)
    project = models.CharField(max_length=200, blank=True)
    seen_profiles = models.ManyToManyField(
        JobSeekerProfile,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.recruiter.username}"

    def criteria(self):
        return {
            "skills": self.skills,
            "location": self.location,
            "project": self.project,
        }
