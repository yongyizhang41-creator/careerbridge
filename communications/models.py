from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from accounts.models import User


class Conversation(models.Model):
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recruiter_conversations",
    )
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["recruiter", "candidate"],
                name="unique_recruiter_candidate_conversation",
            ),
            models.CheckConstraint(
                condition=~Q(recruiter=F("candidate")),
                name="conversation_participants_are_distinct",
            ),
        ]
        indexes = [
            models.Index(fields=["recruiter", "-updated_at"]),
            models.Index(fields=["candidate", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.recruiter} and {self.candidate}"

    def clean(self):
        errors = {}
        if self.recruiter_id and self.recruiter.role != User.Role.RECRUITER:
            errors["recruiter"] = (
                "The recruiter participant must have the recruiter role."
            )
        if self.candidate_id and self.candidate.role != User.Role.JOB_SEEKER:
            errors["candidate"] = (
                "The candidate participant must have the job seeker role."
            )
        if self.recruiter_id and self.recruiter_id == self.candidate_id:
            errors["candidate"] = "Conversation participants must be different users."
        if errors:
            raise ValidationError(errors)

    def includes(self, user):
        return user.pk in (self.recruiter_id, self.candidate_id)

    def other_participant(self, user):
        if user.pk == self.recruiter_id:
            return self.candidate
        if user.pk == self.candidate_id:
            return self.recruiter
        raise ValueError("User is not a participant in this conversation.")


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_platform_messages",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["conversation", "read_at"]),
        ]

    def __str__(self):
        return f"Message from {self.sender} in conversation {self.conversation_id}"

    def clean(self):
        if (
            self.sender_id
            and self.conversation_id
            and not self.conversation.includes(self.sender)
        ):
            raise ValidationError(
                {"sender": "The sender must belong to this conversation."}
            )
