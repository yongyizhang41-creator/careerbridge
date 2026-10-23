from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import JobSeekerProfile, User
from jobs.models import Application, Job

from .models import Conversation, Message


class MessagingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.candidate = User.objects.create_user(
            username="candidate",
            first_name="Casey",
            last_name="Candidate",
            role=User.Role.JOB_SEEKER,
        )
        cls.other_candidate = User.objects.create_user(
            username="other-candidate",
            role=User.Role.JOB_SEEKER,
        )
        JobSeekerProfile.objects.create(
            user=cls.other_candidate,
            recruiter_visible=True,
        )
        cls.recruiter = User.objects.create_user(
            username="recruiter",
            first_name="Riley",
            last_name="Recruiter",
            role=User.Role.RECRUITER,
        )
        cls.other_recruiter = User.objects.create_user(
            username="other-recruiter",
            role=User.Role.RECRUITER,
        )
        cls.admin = User.objects.create_user(
            username="administrator",
            role=User.Role.ADMINISTRATOR,
        )
        cls.job = Job.objects.create(
            recruiter=cls.recruiter,
            title="Software Engineer",
            company="Example Company",
            description="Build useful software.",
        )
        cls.application = Application.objects.create(
            job=cls.job,
            applicant=cls.candidate,
        )
        cls.conversation = Conversation.objects.create(
            recruiter=cls.recruiter,
            candidate=cls.candidate,
        )
        cls.initial_message = Message.objects.create(
            conversation=cls.conversation,
            sender=cls.recruiter,
            body="Thanks for applying. Are you available Tuesday?",
        )

    def setUp(self):
        self.inbox_url = reverse("communications:inbox")
        self.detail_url = reverse("communications:detail", args=[self.conversation.pk])
        self.start_url = reverse("communications:start", args=[self.other_candidate.pk])

    def test_recruiter_and_candidate_have_private_scoped_inboxes(self):
        for user, expected_name in (
            (self.recruiter, "Casey Candidate"),
            (self.candidate, "Riley Recruiter"),
        ):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(self.inbox_url)
                self.assertContains(response, expected_name)
                self.assertContains(response, self.initial_message.body)
                self.assertContains(response, self.detail_url)

        for user in (self.other_recruiter, self.other_candidate):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(self.inbox_url)
                self.assertContains(response, "No messages yet")
                self.assertNotContains(response, self.initial_message.body)

    def test_recruiter_starts_conversation_without_exposing_personal_email(self):
        self.other_candidate.email = "private@example.com"
        self.other_candidate.save(update_fields=["email"])
        self.client.force_login(self.recruiter)

        response = self.client.get(self.start_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start the conversation")
        self.assertNotContains(response, self.other_candidate.email)
        self.assertEqual(Conversation.objects.count(), 1)

        response = self.client.post(
            self.start_url,
            {"body": "  I would like to discuss an opportunity.  "},
        )
        conversation = Conversation.objects.get(candidate=self.other_candidate)
        message = conversation.messages.get()
        self.assertRedirects(
            response,
            reverse("communications:detail", args=[conversation.pk]),
        )
        self.assertEqual(message.sender, self.recruiter)
        self.assertEqual(message.body, "I would like to discuss an opportunity.")

    def test_posting_to_existing_start_url_does_not_drop_message(self):
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("communications:start", args=[self.candidate.pk]),
            {"body": "A second message"},
        )
        self.assertRedirects(response, self.detail_url)
        self.assertTrue(
            self.conversation.messages.filter(body="A second message").exists()
        )
        self.assertEqual(
            Conversation.objects.filter(
                recruiter=self.recruiter,
                candidate=self.candidate,
            ).count(),
            1,
        )

    def test_both_participants_can_send_messages(self):
        cases = (
            (self.recruiter, "Recruiter follow-up"),
            (self.candidate, "Candidate reply"),
        )
        for user, body in cases:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post(self.detail_url, {"body": body})
                self.assertRedirects(response, self.detail_url)
                self.assertTrue(
                    Message.objects.filter(
                        conversation=self.conversation,
                        sender=user,
                        body=body,
                    ).exists()
                )

    def test_sender_and_conversation_are_bound_on_the_server(self):
        other_conversation = Conversation.objects.create(
            recruiter=self.other_recruiter,
            candidate=self.other_candidate,
        )
        self.client.force_login(self.candidate)
        self.client.post(
            self.detail_url,
            {
                "body": "My safe reply",
                "sender": self.other_recruiter.pk,
                "conversation": other_conversation.pk,
            },
        )
        message = Message.objects.get(body="My safe reply")
        self.assertEqual(message.sender, self.candidate)
        self.assertEqual(message.conversation, self.conversation)

    def test_nonparticipants_cannot_read_or_post_to_a_conversation(self):
        for user in (self.other_recruiter, self.other_candidate):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.detail_url).status_code, 404)
                self.assertEqual(
                    self.client.post(
                        self.detail_url, {"body": "Intrusion"}
                    ).status_code,
                    404,
                )
        self.assertFalse(Message.objects.filter(body="Intrusion").exists())

    def test_anonymous_and_administrator_access_is_rejected(self):
        for url in (self.inbox_url, self.detail_url, self.start_url):
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('accounts:login')}?next={url}",
                )

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.inbox_url).status_code, 403)
        self.assertEqual(self.client.get(self.detail_url).status_code, 403)
        self.assertEqual(self.client.get(self.start_url).status_code, 403)

    def test_only_recruiters_can_start_conversations(self):
        for user in (self.candidate, self.other_candidate, self.admin):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.start_url).status_code, 403)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_start_target_must_be_an_active_job_seeker(self):
        self.client.force_login(self.recruiter)
        for user in (self.recruiter, self.other_recruiter, self.admin):
            with self.subTest(role=user.role):
                url = reverse("communications:start", args=[user.pk])
                self.assertEqual(self.client.get(url).status_code, 404)

        self.other_candidate.is_active = False
        self.other_candidate.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.start_url).status_code, 404)

    def test_blank_and_oversized_messages_are_rejected(self):
        self.client.force_login(self.candidate)
        original_count = Message.objects.count()
        for body in (None, "   ", "x" * 2001):
            with self.subTest(length=None if body is None else len(body)):
                data = {} if body is None else {"body": body}
                response = self.client.post(self.detail_url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors.get("body"))
                self.assertEqual(Message.objects.count(), original_count)

        response = self.client.post(self.detail_url, {"body": "x" * 2000})
        self.assertRedirects(response, self.detail_url)
        self.assertEqual(Message.objects.latest("pk").body, "x" * 2000)

    def test_message_content_is_escaped(self):
        unsafe = '<script>alert("message")</script>'
        Message.objects.create(
            conversation=self.conversation,
            sender=self.candidate,
            body=unsafe,
        )
        self.client.force_login(self.recruiter)
        response = self.client.get(self.detail_url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")

    def test_opening_thread_marks_only_incoming_messages_read(self):
        self.client.force_login(self.recruiter)
        self.client.get(self.detail_url)
        self.initial_message.refresh_from_db()
        self.assertIsNone(self.initial_message.read_at)

        reply = Message.objects.create(
            conversation=self.conversation,
            sender=self.candidate,
            body="Incoming reply",
        )
        self.client.get(self.detail_url)
        reply.refresh_from_db()
        self.assertIsNotNone(reply.read_at)

        self.client.force_login(self.candidate)
        self.client.get(self.detail_url)
        self.initial_message.refresh_from_db()
        self.assertIsNotNone(self.initial_message.read_at)

    def test_inbox_unread_count_updates_after_thread_is_opened(self):
        self.client.force_login(self.candidate)
        response = self.client.get(self.inbox_url)
        self.assertEqual(response.context["conversations"][0].unread_count, 1)
        self.assertContains(response, "1 unread")
        self.client.get(self.detail_url)
        response = self.client.get(self.inbox_url)
        self.assertEqual(response.context["conversations"][0].unread_count, 0)
        self.assertNotContains(response, "1 unread")

    def test_model_validation_enforces_roles_and_participants(self):
        invalid_conversation = Conversation(
            recruiter=self.candidate,
            candidate=self.recruiter,
        )
        with self.assertRaises(ValidationError):
            invalid_conversation.full_clean()

        invalid_message = Message(
            conversation=self.conversation,
            sender=self.other_candidate,
            body="Not a participant",
        )
        with self.assertRaises(ValidationError):
            invalid_message.full_clean()

    def test_database_prevents_duplicate_participant_pair(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Conversation.objects.create(
                recruiter=self.recruiter,
                candidate=self.candidate,
            )

    def test_csrf_token_is_required_to_send(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.candidate)
        self.assertEqual(
            client.post(self.detail_url, {"body": "No token"}).status_code,
            403,
        )
        client.get(self.detail_url)
        response = client.post(
            self.detail_url,
            {
                "body": "Token protected",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )
        self.assertRedirects(response, self.detail_url)

    def test_navigation_and_application_review_link_to_messaging(self):
        for user in (self.recruiter, self.candidate):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertContains(
                    self.client.get(reverse("accounts:dashboard")),
                    self.inbox_url,
                )

        self.client.force_login(self.recruiter)
        start_url = reverse("communications:start", args=[self.candidate.pk])
        self.assertContains(
            self.client.get(
                reverse("jobs:application_detail", args=[self.application.pk])
            ),
            start_url,
        )
        self.assertContains(
            self.client.get(reverse("jobs:job_applications", args=[self.job.pk])),
            start_url,
        )
