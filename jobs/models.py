from django.conf import settings
from django.db import models


class Job(models.Model):
    class RemoteType(models.TextChoices):
        REMOTE = "remote", "Remote"
        ON_SITE = "on_site", "On-site"
        HYBRID = "hybrid", "Hybrid"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    description = models.TextField()
    address = models.CharField(max_length=300, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    remote_type = models.CharField(
        max_length=10,
        choices=RemoteType.choices,
        default=RemoteType.ON_SITE,
    )
    visa_sponsorship = models.BooleanField(default=False)
    skills = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated, e.g. Python, Django, SQL",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} @ {self.company}"

    def skill_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    @property
    def has_location(self):
        return self.lat is not None and self.lng is not None


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        REVIEW = "review", "Review"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        CLOSED = "closed", "Closed"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    note = models.TextField(blank=True, max_length=2000)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.APPLIED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "applicant"], name="unique_job_application"
            ),
        ]

    def __str__(self):
        return f"{self.applicant} applied to {self.job}"


class CartItem(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_cart_items"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="cart_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "job"], name="unique_job_cart_item"),
        ]

    def __str__(self):
        return f"{self.owner} saved {self.job}"
