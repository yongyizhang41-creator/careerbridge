import csv
import io

from django.test import TestCase
from django.urls import reverse
from jobs.models import Application, Job

from .models import User


class SharedVisualSystemTests(TestCase):
    """Protect the shared page shell while feature apps grow around it."""

    def test_public_account_pages_use_the_shared_template_and_stylesheet(self):
        for route_name in ("login", "register", "registration_complete"):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(f"accounts:{route_name}"))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "base.html")
                self.assertContains(response, 'class="site-header"')
                self.assertContains(response, 'css/app.css')
                self.assertContains(response, 'name="viewport"')

    def test_dashboard_presents_the_signed_in_users_role(self):
        user = User.objects.create_user(
            username="alex",
            password="test-password-123",
            role=User.Role.JOB_SEEKER,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "Job Seeker")
        self.assertContains(response, reverse("accounts:job_seeker_area"))

    def test_role_denial_uses_the_shared_error_page(self):
        recruiter = User.objects.create_user(
            username="riley",
            password="test-password-123",
            role=User.Role.RECRUITER,
        )
        self.client.force_login(recruiter)

        response = self.client.get(reverse("accounts:job_seeker_area"))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "Permission denied", status_code=403)

    def test_registration_form_has_visible_labels_and_field_errors(self):
        response = self.client.post(
            reverse("accounts:register"),
            data={"username": "", "email": "bad", "role": "job_seeker"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'for="id_username"')
        self.assertContains(response, "form-field--invalid")


class AdministratorCsvExportTests(TestCase):
    def setUp(self):
        self.administrator = User.objects.create_user(
            username="admin-user",
            password="test-password-123",
            role=User.Role.ADMINISTRATOR,
        )
        self.job_seeker = User.objects.create_user(
            username="job-seeker",
            password="test-password-123",
            email="private@example.com",
            role=User.Role.JOB_SEEKER,
        )
        self.recruiter = User.objects.create_user(
            username="recruiter",
            password="test-password-123",
            role=User.Role.RECRUITER,
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title="=Spreadsheet Developer",
            company="CareerBridge",
            description="Build reporting tools.",
            remote_type=Job.RemoteType.HYBRID,
        )
        self.application = Application.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            note="Private candidate note",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        for route_name in (
            "export_users_csv",
            "export_jobs_csv",
            "export_applications_csv",
        ):
            with self.subTest(route_name=route_name):
                report_url = reverse(f"accounts:{route_name}")
                response = self.client.get(report_url)

                self.assertRedirects(
                    response,
                    f'{reverse("accounts:login")}?next={report_url}',
                )

    def test_non_administrator_receives_permission_denied(self):
        self.client.force_login(self.recruiter)

        for route_name in (
            "reporting",
            "export_users_csv",
            "export_jobs_csv",
            "export_applications_csv",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(f"accounts:{route_name}"))

                self.assertEqual(response.status_code, 403)

    def test_reporting_page_shows_role_counts_and_download_action(self):
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("accounts:reporting"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account_counts"]["total"], 3)
        self.assertEqual(response.context["account_counts"]["job_seekers"], 1)
        self.assertEqual(response.context["account_counts"]["recruiters"], 1)
        self.assertEqual(response.context["account_counts"]["administrators"], 1)
        self.assertEqual(response.context["job_counts"]["total"], 1)
        self.assertEqual(response.context["job_counts"]["active"], 1)
        self.assertEqual(response.context["job_counts"]["removed"], 0)
        self.assertEqual(response.context["application_count"], 1)
        self.assertContains(response, reverse("accounts:export_users_csv"))
        self.assertContains(response, reverse("accounts:export_jobs_csv"))
        self.assertContains(response, reverse("accounts:export_applications_csv"))

    def test_csv_has_download_headers_and_stable_columns(self):
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("accounts:export_users_csv"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertRegex(
            response["Content-Disposition"],
            r'^attachment; filename="careerbridge-user-report-\d{4}-\d{2}-\d{2}\.csv"$',
        )
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
        self.assertEqual(
            rows[0],
            [
                "user_id",
                "username",
                "role",
                "is_active",
                "date_joined",
                "last_login",
            ],
        )
        self.assertEqual(
            [row[1] for row in rows[1:]],
            ["admin-user", "job-seeker", "recruiter"],
        )

    def test_csv_excludes_sensitive_account_fields(self):
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("accounts:export_users_csv"))
        csv_text = response.content.decode("utf-8")

        self.assertNotIn("password", csv_text)
        self.assertNotIn("private@example.com", csv_text)
        self.assertNotIn("user_permissions", csv_text)

    def test_csv_neutralizes_spreadsheet_formula_prefixes(self):
        User.objects.create_user(
            username="@dangerous",
            password="test-password-123",
            role=User.Role.JOB_SEEKER,
        )
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("accounts:export_users_csv"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

        self.assertEqual(rows[-1][1], "'@dangerous")

    def test_job_csv_has_stable_privacy_conscious_columns(self):
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("accounts:export_jobs_csv"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response["Content-Disposition"],
            r'^attachment; filename="careerbridge-job-report-\d{4}-\d{2}-\d{2}\.csv"$',
        )
        self.assertEqual(
            rows[0],
            [
                "job_id",
                "title",
                "company",
                "recruiter_username",
                "remote_type",
                "status",
                "created_at",
            ],
        )
        self.assertEqual(rows[1][1], "'=Spreadsheet Developer")
        self.assertEqual(rows[1][2:6], ["CareerBridge", "recruiter", "hybrid", "active"])

    def test_application_csv_excludes_private_content(self):
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("accounts:export_applications_csv"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
        csv_text = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            rows[0],
            [
                "application_id",
                "job_id",
                "job_title",
                "company",
                "applicant_username",
                "created_at",
            ],
        )
        self.assertEqual(rows[1][2], "'=Spreadsheet Developer")
        self.assertEqual(rows[1][4], "job-seeker")
        self.assertNotIn("Private candidate note", csv_text)
        self.assertNotIn("private@example.com", csv_text)
