from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import JobSeekerProfile, User
from communications.models import Conversation
from jobs.models import Application, Job
from .models import Report


class ReportFixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.candidate = User.objects.create_user(username="private-candidate", role=User.Role.JOB_SEEKER)
        cls.profile = JobSeekerProfile.objects.create(user=cls.candidate, recruiter_visible=False)
        cls.other_candidate = User.objects.create_user(username="other-candidate", role=User.Role.JOB_SEEKER)
        cls.recruiter = User.objects.create_user(username="reporting-recruiter", role=User.Role.RECRUITER)
        cls.other_recruiter = User.objects.create_user(username="unrelated-recruiter", role=User.Role.RECRUITER)
        cls.admin = User.objects.create_user(username="report-admin", role=User.Role.ADMINISTRATOR)
        cls.job = Job.objects.create(recruiter=cls.recruiter, title="Reported job", company="Example", description="Original evidence")

    def setUp(self):
        self.client.force_login(self.recruiter)
        self.user_url = reverse("reports:user", args=[self.candidate.pk])
        self.job_url = reverse("reports:job", args=[self.job.pk])
        self.data = {"reason": "spam", "details": "Repeated unsolicited content."}

    def assert_candidate_report_allowed(self):
        self.assertContains(self.client.get(self.user_url), self.candidate.username)
        self.assertRedirects(self.client.post(self.user_url, self.data), reverse("reports:submitted"))
        self.assertEqual(Report.objects.get().reported_user, self.candidate)

    def test_hidden_or_missing_profile_blocks_get_and_post_without_leaking_username(self):
        Application.objects.create(applicant=self.candidate, job=self.job)
        Conversation.objects.create(recruiter=self.recruiter, candidate=self.candidate)
        self.client.force_login(self.other_recruiter)
        for has_profile in (True, False):
            if not has_profile:
                self.profile.delete()
            for method in (self.client.get, self.client.post):
                with self.subTest(has_profile=has_profile, method=method.__name__):
                    response = method(self.user_url, self.data)
                    self.assertNotContains(response, self.candidate.username, status_code=404)
        self.assertFalse(Report.objects.exists())

    def test_recruiter_can_report_visible_candidate(self):
        self.profile.recruiter_visible = True
        self.profile.save()
        self.assert_candidate_report_allowed()

    def test_recruiter_can_report_hidden_applicant_even_without_profile(self):
        self.profile.delete()
        Application.objects.create(applicant=self.candidate, job=self.job)
        self.assert_candidate_report_allowed()

    def test_recruiter_can_report_hidden_conversation_partner(self):
        Conversation.objects.create(recruiter=self.recruiter, candidate=self.candidate)
        self.assert_candidate_report_allowed()

    def test_admin_can_report_hidden_candidate(self):
        self.client.force_login(self.admin)
        self.assert_candidate_report_allowed()

    def test_other_job_seeker_cannot_report_candidate_even_if_recruiter_visible(self):
        self.profile.recruiter_visible = True
        self.profile.save()
        self.client.force_login(self.other_candidate)
        self.assertEqual(self.client.get(self.user_url).status_code, 404)
        self.assertEqual(self.client.post(self.user_url, self.data).status_code, 404)
        self.assertFalse(Report.objects.exists())

    def test_open_duplicate_reports_are_blocked_for_both_target_types_and_statuses(self):
        self.client.force_login(self.other_candidate)
        recruiter_url = reverse("reports:user", args=[self.recruiter.pk])
        for url in (self.job_url, recruiter_url):
            for status in (Report.Status.PENDING, Report.Status.INVESTIGATING):
                with self.subTest(url=url, status=status):
                    self.client.post(url, self.data)
                    original = Report.objects.get()
                    original.status = status
                    original.save()
                    response = self.client.post(url, {**self.data, "details": "Replacement evidence"}, follow=True)
                    self.assertRedirects(response, reverse("reports:submitted"))
                    self.assertContains(response, "You already reported this.")
                    self.assertEqual(Report.objects.count(), 1)
                    original.refresh_from_db()
                    self.assertEqual(original.details, self.data["details"])
                    self.assertEqual(original.status, status)
                    Report.objects.all().delete()

    def test_resolved_reports_allow_new_report_for_both_target_types(self):
        self.client.force_login(self.other_candidate)
        for url in (self.job_url, reverse("reports:user", args=[self.recruiter.pk])):
            with self.subTest(url=url):
                self.client.post(url, self.data)
                Report.objects.update(status=Report.Status.RESOLVED, review_notes="Reviewed.")
                self.assertRedirects(self.client.post(url, self.data), reverse("reports:submitted"))
                self.assertEqual(Report.objects.filter(status=Report.Status.PENDING).count(), 1)
                self.assertEqual(Report.objects.filter(status=Report.Status.RESOLVED).count(), 1)
                Report.objects.all().delete()

    def test_duplicate_check_does_not_block_different_reporters_or_targets(self):
        self.client.force_login(self.candidate)
        self.client.post(self.job_url, self.data)
        self.client.force_login(self.other_candidate)
        self.client.post(self.job_url, self.data)
        self.client.post(reverse("reports:user", args=[self.recruiter.pk]), self.data)
        other_job = Job.objects.create(recruiter=self.recruiter, title="Another job", company="Example", description="Different target")
        self.client.post(reverse("reports:job", args=[other_job.pk]), self.data)
        self.assertEqual(Report.objects.count(), 4)

    def test_detail_removal_preserves_permissions_csrf_evidence_and_restore(self):
        self.client.post(self.job_url, self.data)
        report = Report.objects.get()
        detail_url = reverse("reports:detail", args=[report.pk])
        remove_url = reverse("jobs:remove", args=[self.job.pk])
        for user in (self.candidate, self.recruiter):
            self.client.force_login(user)
            self.assertEqual(self.client.get(detail_url).status_code, 403)
            self.assertEqual(self.client.post(remove_url).status_code, 403)

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.get(detail_url)
        self.assertContains(response, f'action="{remove_url}"')
        self.assertContains(response, "Remove this job post")
        self.assertEqual(client.get(remove_url).status_code, 405)
        self.assertEqual(client.post(remove_url).status_code, 403)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.ACTIVE)
        token = {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        self.assertRedirects(client.post(remove_url, token), reverse("jobs:moderation"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.REMOVED)
        self.assertNotContains(client.get(detail_url), f'action="{remove_url}"')
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.PENDING)
        self.assertIn("Original evidence", report.target_snapshot)
        self.assertRedirects(client.post(reverse("jobs:restore", args=[self.job.pk]), token), reverse("jobs:moderation"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.ACTIVE)
        self.assertContains(client.get(detail_url), f'action="{remove_url}"')
