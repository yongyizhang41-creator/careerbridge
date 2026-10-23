from smtplib import SMTPException
from unittest.mock import ANY, patch

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import JobSeekerProfile, User
from jobs.models import Application, Job

from .models import Conversation, Message


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="outreach@careerbridge.example",
)
class CandidateContactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.recruiter = User.objects.create_user(
            username="recruiter", first_name="Riley", last_name="Recruiter",
            email="riley@example.com", role=User.Role.RECRUITER,
        )
        cls.candidate = User.objects.create_user(
            username="candidate", email="casey@example.com",
            role=User.Role.JOB_SEEKER,
        )
        cls.profile = JobSeekerProfile.objects.create(
            user=cls.candidate, recruiter_visible=True,
        )
        cls.admin = User.objects.create_user(
            username="admin", role=User.Role.ADMINISTRATOR,
        )
        cls.job = Job.objects.create(
            recruiter=cls.recruiter, title="Engineer", company="Example",
            description="Build useful software.",
        )

    def setUp(self):
        self.url = reverse("communications:email", args=[self.candidate.pk])
        self.start_url = reverse("communications:start", args=[self.candidate.pk])
        self.draft = {"subject": "Interview opportunity", "body": "Are you available Tuesday?"}
        self.client.force_login(self.recruiter)

    def test_compose_get_does_not_send_email_or_create_conversation(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.candidate.email)
        self.assertContains(response, self.recruiter.email)
        self.assertContains(response, "Send email")
        self.assertContains(response, self.start_url)
        self.assertFalse(mail.outbox)
        self.assertFalse(Conversation.objects.exists())

    def test_send_uses_server_bound_recipient_sender_and_reply_address(self):
        response = self.client.post(self.url, {
            "subject": "  Interview opportunity  ",
            "body": "  Are you available Tuesday?  ",
            "to": "intruder@example.com", "from_email": "spoofed@example.com",
            "reply_to": "intruder@example.com", "candidate": self.admin.pk,
        }, follow=True)
        self.assertRedirects(response, self.url)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.candidate.email])
        self.assertEqual(email.from_email, "outreach@careerbridge.example")
        self.assertEqual(email.reply_to, [self.recruiter.email])
        self.assertEqual(email.subject, "Interview opportunity")
        self.assertEqual(email.content_subtype, "plain")
        self.assertEqual(email.body, "Riley Recruiter sent you an email through CareerBridge.\n\nAre you available Tuesday?")
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(Message.objects.exists())
        self.assertContains(response, "accepted by the mail server")
        self.client.get(self.url)
        self.assertEqual(len(mail.outbox), 1)

    def test_only_recruiters_can_compose_or_send(self):
        self.client.logout()
        for method in (self.client.get, self.client.post):
            self.assertRedirects(
                method(self.url), f"{reverse('accounts:login')}?next={self.url}",
            )
        for user in (self.candidate, self.admin):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, self.draft).status_code, 403)
        self.assertFalse(mail.outbox)

    def test_target_must_be_an_active_job_seeker(self):
        for user in (self.recruiter, self.admin):
            url = reverse("communications:email", args=[user.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, self.draft).status_code, 404)
        self.candidate.is_active = False
        self.candidate.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.draft).status_code, 404)
        self.assertFalse(mail.outbox)

    def test_hidden_candidates_cannot_be_contacted_by_guessing_ids(self):
        self.profile.recruiter_visible = False
        self.profile.save(update_fields=["recruiter_visible"])
        other_recruiter = User.objects.create_user(
            username="other-recruiter", role=User.Role.RECRUITER,
        )
        Conversation.objects.create(recruiter=other_recruiter, candidate=self.candidate)
        other_job = Job.objects.create(
            recruiter=other_recruiter, title="Other job", company="Other",
        )
        Application.objects.create(job=other_job, applicant=self.candidate)
        for url in (self.url, self.start_url):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, self.draft).status_code, 404)
        self.assertFalse(mail.outbox)

    def test_own_applicants_can_be_contacted_without_a_public_profile(self):
        self.profile.delete()
        Application.objects.create(job=self.job, applicant=self.candidate)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(self.start_url).status_code, 200)
        self.assertRedirects(self.client.post(self.url, self.draft), self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post(self.start_url, {"body": "Hello"}).status_code, 302)

    def test_existing_conversations_remain_contactable_after_privacy_change(self):
        self.profile.recruiter_visible = False
        self.profile.save(update_fields=["recruiter_visible"])
        conversation = Conversation.objects.create(
            recruiter=self.recruiter, candidate=self.candidate,
        )
        self.assertRedirects(self.client.post(self.url, self.draft), self.url)
        self.assertRedirects(
            self.client.post(self.start_url, {"body": "Follow-up"}),
            reverse("communications:detail", args=[conversation.pk]),
        )

    def test_invalid_subjects_and_bodies_do_not_send(self):
        for field, invalid in (
            ("subject", ""), ("subject", "   "), ("subject", "x" * 201),
            ("subject", "Hello\nBcc: intruder@example.com"),
            ("subject", "Hello\rBcc: intruder@example.com"),
            ("body", ""), ("body", "  "), ("body", "x" * 10001),
        ):
            with self.subTest(field=field, value=invalid[:30]):
                response = self.client.post(self.url, {**self.draft, field: invalid})
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
        self.assertFalse(mail.outbox)

    def test_missing_or_invalid_account_email_prevents_sending(self):
        for user in (self.candidate, self.recruiter):
            original_email = user.email
            for invalid in ("", "invalid", "valid@example.com\nBcc: victim@example.com"):
                with self.subTest(user=user.username, email=invalid):
                    user.email = invalid
                    user.save(update_fields=["email"])
                    response = self.client.post(self.url, self.draft)
                    self.assertContains(response, "valid email address")
                    self.assertContains(response, "disabled")
            user.email = original_email
            user.save(update_fields=["email"])
        self.assertFalse(mail.outbox)

    def test_unconfigured_sender_host_or_password_prevents_sending(self):
        for overrides in (
            {"DEFAULT_FROM_EMAIL": ""},
            {"EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": ""},
            {
                "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "EMAIL_HOST_USER": "careerbridgemessage@gmail.com", "EMAIL_HOST_PASSWORD": "",
            },
        ):
            with self.subTest(overrides=overrides), override_settings(**overrides):
                response = self.client.post(self.url, self.draft)
                self.assertContains(response, "Email delivery is not configured")
                self.assertContains(response, "disabled")
        self.assertFalse(mail.outbox)

    def test_delivery_errors_keep_the_draft_without_exposing_server_details(self):
        for error in (SMTPException("secret SMTP credentials"), OSError("private host")):
            with self.subTest(error=error), patch("communications.views.EmailMessage.send", side_effect=error):
                response = self.client.post(self.url, self.draft)
                self.assertContains(response, "The email could not be sent")
                self.assertContains(response, self.draft["subject"])
                self.assertContains(response, self.draft["body"])
                self.assertNotContains(response, str(error))
        with patch("communications.views.EmailMessage.send", return_value=0):
            self.assertContains(self.client.post(self.url, self.draft), "The email could not be sent")
        self.assertFalse(mail.outbox)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com", EMAIL_PORT=587,
        EMAIL_HOST_USER="smtp-user", EMAIL_HOST_PASSWORD="test-password",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
    )
    def test_smtp_backend_uses_configured_transport_and_headers(self):
        with patch("smtplib.SMTP") as smtp:
            self.assertRedirects(self.client.post(self.url, self.draft), self.url)
            smtp.assert_called_once_with("smtp.example.com", 587, local_hostname=ANY, timeout=10)
            smtp.return_value.starttls.assert_called_once()
            smtp.return_value.login.assert_called_once_with("smtp-user", "test-password")
            sender, recipients, payload = smtp.return_value.sendmail.call_args.args
            self.assertEqual(sender, "outreach@careerbridge.example")
            self.assertEqual(recipients, [self.candidate.email])
            self.assertIn(b"Reply-To: riley@example.com", payload)

    def test_csrf_token_and_supported_http_method_are_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.recruiter)
        self.assertEqual(client.post(self.url, self.draft).status_code, 403)
        client.get(self.url)
        response = client.post(self.url, {
            **self.draft, "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertEqual(self.client.delete(self.url).status_code, 405)

    def test_contact_links_exist_on_candidate_and_application_pages(self):
        application = Application.objects.create(job=self.job, applicant=self.candidate)
        conversation = Conversation.objects.create(recruiter=self.recruiter, candidate=self.candidate)
        for page in (
            reverse("accounts:candidate_search"),
            reverse("jobs:candidate_profile", args=[self.job.pk, self.profile.pk]),
            reverse("jobs:application_detail", args=[application.pk]),
            reverse("jobs:job_applications", args=[self.job.pk]),
        ):
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertContains(response, self.url)
                self.assertContains(response, self.start_url)
        detail_url = reverse("communications:detail", args=[conversation.pk])
        self.assertContains(self.client.get(detail_url), self.url)
        self.client.force_login(self.candidate)
        self.assertNotContains(self.client.get(detail_url), self.url)
