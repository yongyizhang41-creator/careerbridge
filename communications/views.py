from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError, EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required
from accounts.models import User

from .forms import CandidateEmailForm, MessageForm
from .models import Conversation, Message

messaging_required = role_required(User.Role.JOB_SEEKER, User.Role.RECRUITER)
recruiter_required = role_required(User.Role.RECRUITER)


def _contactable_candidate(recruiter, candidate_pk):
    return get_object_or_404(
        User.objects.filter(
            Q(job_seeker_profile__recruiter_visible=True)
            | Q(applications__job__recruiter=recruiter)
            | Q(candidate_conversations__recruiter=recruiter)
        ).distinct(),
        pk=candidate_pk,
        role=User.Role.JOB_SEEKER,
        is_active=True,
    )


def _participant_conversations(user):
    if user.role == User.Role.RECRUITER:
        return Conversation.objects.filter(recruiter=user)
    return Conversation.objects.filter(candidate=user)


def _conversation_list(user):
    latest = Message.objects.filter(conversation=OuterRef("pk")).order_by(
        "-created_at", "-pk"
    )
    conversations = (
        _participant_conversations(user)
        .select_related("recruiter", "candidate")
        .annotate(
            latest_body=Subquery(latest.values("body")[:1]),
            latest_created_at=Subquery(latest.values("created_at")[:1]),
            unread_count=Count(
                "messages",
                filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user),
            ),
        )
        .order_by("-updated_at", "-pk")
    )
    for conversation in conversations:
        conversation.other_user = conversation.other_participant(user)
    return conversations


def _thread_context(user, conversation, form):
    other_user = conversation.other_participant(user)
    return {
        "conversation": conversation,
        "conversation_messages": conversation.messages.select_related("sender"),
        "form": form,
        "other_user": other_user,
    }


@transaction.atomic
def _save_message(conversation, sender, form):
    message = form.save(commit=False)
    message.conversation = conversation
    message.sender = sender
    message.full_clean()
    message.save()
    conversation.save(update_fields=["updated_at"])
    return message


@messaging_required
def inbox(request):
    return render(
        request,
        "communications/inbox.html",
        {"conversations": _conversation_list(request.user)},
    )


@recruiter_required
@require_http_methods(["GET", "POST"])
def start_conversation(request, candidate_pk):
    candidate = _contactable_candidate(request.user, candidate_pk)
    existing = Conversation.objects.filter(
        recruiter=request.user,
        candidate=candidate,
    ).first()
    if existing and request.method == "GET":
        return redirect("communications:detail", pk=existing.pk)

    form = MessageForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            conversation = existing
            if conversation is None:
                conversation, _ = Conversation.objects.get_or_create(
                    recruiter=request.user,
                    candidate=candidate,
                )
            _save_message(conversation, request.user, form)
        messages.success(request, "Message sent.")
        return redirect("communications:detail", pk=conversation.pk)

    return render(
        request,
        "communications/conversation.html",
        {
            "conversation": None,
            "conversation_messages": (),
            "form": form,
            "other_user": candidate,
        },
    )


@messaging_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        _participant_conversations(request.user).select_related(
            "recruiter", "candidate"
        ),
        pk=pk,
    )
    conversation.messages.filter(read_at__isnull=True).exclude(
        sender=request.user
    ).update(read_at=timezone.now())

    form = MessageForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        _save_message(conversation, request.user, form)
        messages.success(request, "Message sent.")
        return redirect("communications:detail", pk=conversation.pk)

    return render(
        request,
        "communications/conversation.html",
        _thread_context(request.user, conversation, form),
    )


@recruiter_required
@require_http_methods(["GET", "POST"])
def email_candidate(request, candidate_pk):
    candidate = _contactable_candidate(request.user, candidate_pk)
    form = CandidateEmailForm(request.POST if request.method == "POST" else None)
    delivery_issue = ""
    for address, error in (
        (candidate.email, "This candidate has no valid email address. Use platform messaging instead."),
        (request.user.email, "Your account needs a valid email address for replies. Ask an administrator to update it."),
        (settings.DEFAULT_FROM_EMAIL, "Email delivery is not configured. Contact an administrator or use platform messaging."),
    ):
        try:
            validate_email(address)
        except ValidationError:
            delivery_issue = error
            break
    if (
        not delivery_issue
        and settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and (
            not settings.EMAIL_HOST
            or (settings.EMAIL_HOST_USER and not settings.EMAIL_HOST_PASSWORD)
        )
    ):
        delivery_issue = "Email delivery is not configured. Contact an administrator or use platform messaging."

    if request.method == "POST" and form.is_valid() and not delivery_issue:
        recruiter_name = request.user.get_full_name() or request.user.username
        email = EmailMessage(
            subject=form.cleaned_data["subject"],
            body=f"{recruiter_name} sent you an email through CareerBridge.\n\n{form.cleaned_data['body']}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[candidate.email],
            reply_to=[request.user.email],
        )
        try:
            sent = email.send(fail_silently=False)
        except (BadHeaderError, SMTPException, OSError):
            sent = 0
        if sent == 1:
            messages.success(request, "Email accepted by the mail server for delivery to the candidate.")
            return redirect("communications:email", candidate_pk=candidate.pk)
        form.add_error(None, "The email could not be sent. Your draft is below. Please try again later or use platform messaging.")

    return render(
        request,
        "communications/email_candidate.html",
        {"candidate": candidate, "form": form, "delivery_issue": delivery_issue},
    )
