from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from jobs.models import Application, Job
from .models import Report


class ReportWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seeker = User.objects.create_user(username="reporter", role=User.Role.JOB_SEEKER)
        cls.recruiter = User.objects.create_user(username="reported-recruiter", role=User.Role.RECRUITER)
        cls.admin = User.objects.create_user(username="reviewer", role=User.Role.ADMINISTRATOR)
        cls.job = Job.objects.create(recruiter=cls.recruiter, title="Original title", company="Example", description="Original evidence")

    def setUp(self):
        self.client.force_login(self.seeker)
        self.job_url = reverse("reports:job", args=[self.job.pk])
        self.user_url = reverse("reports:user", args=[self.recruiter.pk])
        self.data = {"reason": "misleading", "details": "The advertised duties do not match the description."}

    def create_report(self):
        self.client.post(self.job_url, self.data)
        return Report.objects.latest("pk")

    def test_submit_job_report_records_actor_target_and_evidence(self):
        self.assertContains(self.client.get(self.job_url), "Original title")
        response = self.client.post(self.job_url, {**self.data, "status": "resolved", "reporter": self.admin.pk, "reported_job": 999999}, follow=True)
        self.assertRedirects(response, reverse("reports:submitted"))
        report = Report.objects.get()
        self.assertEqual(report.reporter, self.seeker)
        self.assertEqual(report.reported_job, self.job)
        self.assertIsNone(report.reported_user)
        self.assertEqual(report.status, Report.Status.PENDING)
        self.assertIn("Original evidence", report.target_snapshot)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.ACTIVE)

    def test_submit_user_report_does_not_suspend_account(self):
        self.assertRedirects(self.client.post(self.user_url, {"reason": "abuse", "details": "Inappropriate messages in our conversation."}), reverse("reports:submitted"))
        report = Report.objects.get()
        self.assertEqual(report.target_type, "user")
        self.assertEqual(report.reported_user, self.recruiter)
        self.assertIsNone(report.reported_job)
        self.recruiter.refresh_from_db()
        self.assertTrue(self.recruiter.is_active)

    def test_snapshot_survives_edits_and_deleted_job(self):
        report = self.create_report()
        self.job.title = "Changed title"
        self.job.description = "Changed evidence"
        self.job.save()
        self.job.delete()
        report.refresh_from_db()
        self.assertIsNone(report.reported_job)
        self.assertIn("Original evidence", report.target_snapshot)
        self.assertIn("Original title", report.target_label)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:detail", args=[report.pk]))
        self.assertContains(response, "Original evidence")
        self.assertContains(response, "has been deleted")

    def test_user_report_survives_deletion_of_target_and_reporter(self):
        self.client.post(self.user_url, {"reason": "spam", "details": "Repeated spam."})
        report = Report.objects.get()
        self.recruiter.delete()
        self.seeker.delete()
        report.refresh_from_db()
        self.assertIsNone(report.reported_user)
        self.assertIsNone(report.reporter)
        self.assertIn("reported-recruiter", report.target_snapshot)

    def test_invalid_submission_does_not_save(self):
        for data in ({"reason": "invalid", "details": "Concern"}, {"reason": "spam", "details": " "}, {"reason": "spam", "details": "x" * 5001}):
            response = self.client.post(self.job_url, data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(Report.objects.exists())

    def test_self_missing_or_unavailable_targets_are_rejected(self):
        self.assertEqual(self.client.post(reverse("reports:user", args=[self.seeker.pk]), self.data).status_code, 403)
        self.assertEqual(self.client.post(reverse("reports:job", args=[999999]), self.data).status_code, 404)
        self.job.status = Job.Status.REMOVED
        self.job.save()
        self.assertEqual(self.client.post(self.job_url, self.data).status_code, 404)
        self.assertFalse(Report.objects.exists())

    def test_anonymous_users_must_log_in(self):
        self.client.logout()
        for url in (self.job_url, self.user_url, reverse("reports:list")):
            response = self.client.get(url)
            self.assertRedirects(response, f'{reverse("accounts:login")}?next={url}')

    def test_only_administrators_can_read_report_or_notes(self):
        report = self.create_report()
        report.review_notes = "Private investigation notes"
        report.save()
        detail_url = reverse("reports:detail", args=[report.pk])
        for user in (self.seeker, self.recruiter):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("reports:list")).status_code, 403)
            self.assertEqual(self.client.get(detail_url).status_code, 403)
            self.assertEqual(self.client.post(detail_url, {"status": "resolved", "review_notes": "Overwrite"}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(detail_url), "Private investigation notes")

    def test_admin_reviews_without_automatic_moderation(self):
        report = self.create_report()
        detail_url = reverse("reports:detail", args=[report.pk])
        self.client.force_login(self.admin)
        for status in Report.Status.values:
            response = self.client.post(detail_url, {"status": status, "review_notes": f"Investigation: {status}"})
            self.assertRedirects(response, detail_url)
            report.refresh_from_db()
            self.assertEqual(report.status, status)
            self.assertEqual(report.reviewed_by, self.admin)
            self.assertIsNotNone(report.reviewed_at)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.ACTIVE)
        self.assertContains(self.client.get(detail_url), reverse("jobs:moderation"))

    def test_resolution_requires_notes_and_cannot_rewrite_evidence(self):
        report = self.create_report()
        self.client.force_login(self.admin)
        url = reverse("reports:detail", args=[report.pk])
        response = self.client.post(url, {"status": "resolved", "review_notes": ""})
        self.assertTrue(response.context["form"].errors)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.PENDING)
        self.client.post(url, {"status": "investigating", "review_notes": "Checking facts", "details": "Overwrite", "reporter": self.admin.pk, "target_snapshot": "Overwrite"})
        report.refresh_from_db()
        self.assertEqual(report.details, self.data["details"])
        self.assertEqual(report.reporter, self.seeker)
        self.assertIn("Original evidence", report.target_snapshot)

    def test_filters_search_and_pagination(self):
        report = self.create_report()
        self.client.post(self.user_url, {"reason": "spam", "details": "Spam account"})
        self.client.force_login(self.admin)
        url = reverse("reports:list")
        response = self.client.get(url, {"type": "job", "status": "pending", "q": "Original"})
        self.assertEqual(list(response.context["page_obj"]), [report])
        self.assertContains(self.client.get(url, {"status": "resolved"}), "No reports found")
        for index in range(26):
            Report.objects.create(reporter=self.seeker, target_type="job", reported_job=self.job, target_label=f"Extra {index}", target_snapshot="Snapshot", reason="spam", details="Details")
        response = self.client.get(url, {"page": "2"})
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(response.context["page_obj"].paginator.count, 28)

    def test_user_management_link_uses_native_pages_and_existing_permissions(self):
        self.client.post(self.user_url, self.data)
        report = Report.objects.get()
        self.client.force_login(self.admin)
        url = reverse("reports:detail", args=[report.pk])
        self.assertNotContains(self.client.get(url), "Open existing user management tools")
        self.admin.is_staff = True
        self.admin.save()
        self.assertNotContains(self.client.get(url), "Open existing user management tools")
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label="accounts", codename="view_user"))
        self.assertContains(self.client.get(url), reverse("accounts:user_management") + "?q=reported-recruiter")
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label="accounts", codename="change_user"))
        self.assertContains(self.client.get(url), reverse("accounts:user_edit", args=[self.recruiter.pk]))
        self.assertEqual(self.client.get(reverse("accounts:user_edit", args=[self.recruiter.pk])).status_code, 200)

    def test_csrf_required_for_submission_and_review(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.seeker)
        self.assertEqual(client.post(self.job_url, self.data).status_code, 403)
        client.get(self.job_url)
        response = client.post(self.job_url, {**self.data, "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        report = Report.objects.get()
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse("reports:detail", args=[report.pk]), {"status": "investigating"}).status_code, 403)

    def test_report_evidence_and_details_are_escaped(self):
        self.job.description = '<script>alert("evidence")</script>'
        self.job.save()
        self.client.post(self.job_url, {"reason": "abuse", "details": '<script>alert("details")</script>'})
        report = Report.objects.get()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:detail", args=[report.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")

    def test_database_rejects_mismatched_target_type(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Report.objects.create(reporter=self.seeker, target_type="job", reported_user=self.recruiter, target_label="Wrong", target_snapshot="Wrong", reason="spam", details="Wrong target")

    def test_entry_points_preserve_existing_workflows(self):
        response = self.client.get(reverse("jobs:detail", args=[self.job.pk]))
        self.assertContains(response, self.job_url)
        self.assertContains(response, self.user_url)
        self.assertContains(response, "Apply now")
        application = Application.objects.create(applicant=self.seeker, job=self.job)
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("jobs:application_detail", args=[application.pk]))
        self.assertContains(response, reverse("reports:user", args=[self.seeker.pk]))
        self.assertContains(response, "Message candidate")
        self.assertContains(response, "Save status")
        response = self.client.get(reverse("communications:start", args=[self.seeker.pk]))
        self.assertContains(response, reverse("reports:user", args=[self.seeker.pk]))
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("accounts:reporting")), reverse("reports:list"))
