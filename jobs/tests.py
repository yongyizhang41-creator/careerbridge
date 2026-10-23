from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from .models import Application, Job


class JobApplicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seeker = User.objects.create_user(username="seeker", role=User.Role.JOB_SEEKER)
        cls.other_seeker = User.objects.create_user(username="other", role=User.Role.JOB_SEEKER)
        cls.recruiter = User.objects.create_user(username="recruiter", role=User.Role.RECRUITER)
        cls.administrator = User.objects.create_user(username="admin", role=User.Role.ADMINISTRATOR)
        cls.job = Job.objects.create(
            recruiter=cls.recruiter, title="Developer", company="Example",
            description="Build useful software.",
        )

    def setUp(self):
        self.detail_url = reverse("jobs:detail", args=[self.job.pk])
        self.apply_url = reverse("jobs:apply", args=[self.job.pk])
        self.client.force_login(self.seeker)

    def test_one_click_application_without_note(self):
        response = self.client.post(self.apply_url, follow=True)
        self.assertRedirects(response, self.detail_url)
        application = Application.objects.get()
        self.assertEqual(application.applicant, self.seeker)
        self.assertEqual(application.job, self.job)
        self.assertEqual(application.note, "")
        self.assertContains(response, "Application submitted")
        self.assertNotContains(response, "Apply now")

    def test_note_is_saved_and_displayed_safely(self):
        note = 'I build Django apps.\n<script>alert("test")</script>'
        response = self.client.post(self.apply_url, {"note": note}, follow=True)
        self.assertEqual(Application.objects.get().note, note)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")
        self.assertContains(self.client.get(self.detail_url), "I build Django apps.")

    def test_duplicate_does_not_replace_original_note(self):
        self.client.post(self.apply_url, {"note": "Original"})
        response = self.client.post(self.apply_url, {"note": "Replacement"}, follow=True)
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(Application.objects.get().note, "Original")
        self.assertContains(response, "already applied")

    def test_database_rejects_duplicate_application(self):
        Application.objects.create(job=self.job, applicant=self.seeker)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Application.objects.create(job=self.job, applicant=self.seeker)

    def test_separate_seekers_can_apply_without_seeing_each_others_note(self):
        self.client.post(self.apply_url, {"note": "Private first note"})
        self.client.force_login(self.other_seeker)
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Apply now")
        self.assertNotContains(response, "Private first note")
        self.client.post(self.apply_url, {"note": "Second note"})
        self.assertEqual(Application.objects.count(), 2)

    def test_posted_applicant_and_job_ids_cannot_override_target(self):
        self.client.post(self.apply_url, {
            "applicant": self.other_seeker.pk, "job": 999999, "note": "My note",
        })
        application = Application.objects.get()
        self.assertEqual(application.applicant, self.seeker)
        self.assertEqual(application.job, self.job)

    def test_invalid_note_keeps_input_and_does_not_create_application(self):
        response = self.client.post(self.apply_url, {"note": "x" * 2001})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["application_form"].errors.get("note"))
        self.assertContains(response, "x" * 2001)
        self.assertFalse(Application.objects.exists())
        self.client.post(self.apply_url, {"note": "x" * 2000})
        self.assertEqual(len(Application.objects.get().note), 2000)

    def test_anonymous_user_must_log_in(self):
        self.client.logout()
        response = self.client.post(self.apply_url)
        self.assertRedirects(response, f'{reverse("accounts:login")}?next={self.apply_url}')
        self.assertContains(self.client.get(self.detail_url), "Log in to apply")
        self.assertFalse(Application.objects.exists())

    def test_other_roles_cannot_apply(self):
        for user in (self.recruiter, self.administrator):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.post(self.apply_url).status_code, 403)
                self.assertNotContains(self.client.get(self.detail_url), "Apply now")
        self.assertFalse(Application.objects.exists())

    def test_get_request_does_not_submit(self):
        self.assertContains(self.client.get(self.detail_url), "Apply now")
        self.assertEqual(self.client.get(self.apply_url).status_code, 405)
        self.assertFalse(Application.objects.exists())

    def test_removed_and_missing_jobs_cannot_receive_applications(self):
        self.job.status = Job.Status.REMOVED
        self.job.save()
        self.assertEqual(self.client.post(self.apply_url).status_code, 404)
        self.assertEqual(self.client.post(reverse("jobs:apply", args=[999999])).status_code, 404)
        self.assertFalse(Application.objects.exists())

    def test_submission_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.seeker)
        self.assertEqual(client.post(self.apply_url).status_code, 403)
        client.get(self.detail_url)
        response = client.post(self.apply_url, {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "note": "Valid submission",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Application.objects.count(), 1)
