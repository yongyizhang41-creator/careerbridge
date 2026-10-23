from django.conf import settings
from django.db import models


class Report(models.Model):
    class TargetType(models.TextChoices):
        JOB = "job", "Job posting"
        USER = "user", "User"

    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        MISLEADING = "misleading", "Misleading content"
        ABUSE = "abuse", "Abusive or inappropriate content"
        OTHER = "other", "Other concern"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        INVESTIGATING = "investigating", "Investigating"
        RESOLVED = "resolved", "Resolved"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="submitted_reports",
    )
    target_type = models.CharField(max_length=4, choices=TargetType.choices)
    reported_job = models.ForeignKey(
        "jobs.Job", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports",
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reports_about",
    )
    # Keep the submitted evidence even if the target is edited or deleted later.
    target_label = models.CharField(max_length=500)
    target_snapshot = models.TextField()
    reason = models.CharField(max_length=12, choices=Reason.choices)
    details = models.TextField(max_length=5000)
    status = models.CharField(max_length=13, choices=Status.choices, default=Status.PENDING)
    review_notes = models.TextField(blank=True, max_length=10000)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(target_type="job", reported_user__isnull=True)
                    | models.Q(target_type="user", reported_job__isnull=True)
                ),
                name="report_target_matches_type",
            ),
        ]

    def __str__(self):
        return f"Report #{self.pk}: {self.target_label}"
