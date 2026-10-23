from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Education, JobSeekerProfile, ProfessionalLink, User, WorkExperience
from .models import Application, Job


class ApplicationReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seeker = User.objects.create_user(username="candidate", role=User.Role.JOB_SEEKER)
        cls.other_seeker = User.objects.create_user(username="other-candidate", role=User.Role.JOB_SEEKER)
        cls.recruiter = User.objects.create_user(username="owner", role=User.Role.RECRUITER)
        cls.other_recruiter = User.objects.create_user(username="other-owner", role=User.Role.RECRUITER)
        cls.admin = User.objects.create_user(username="administrator", role=User.Role.ADMINISTRATOR)
        cls.job = Job.objects.create(recruiter=cls.recruiter, title="Engineer", company="Example", description="Build apps")
        cls.other_job = Job.objects.create(recruiter=cls.other_recruiter, title="Other job", company="Other", description="Other work")
        cls.application = Application.objects.create(job=cls.job, applicant=cls.seeker, note="My tailored note")
        cls.other_application = Application.objects.create(job=cls.other_job, applicant=cls.other_seeker, note="Another private note")
        cls.profile = JobSeekerProfile.objects.create(user=cls.seeker, headline="Django developer", skills="Python, SQL", location="Atlanta")
        Education.objects.create(profile=cls.profile, institution="Example University", degree="BS", field_of_study="Computer Science", start_date="2022-08-01", end_date="2026-05-01")
        WorkExperience.objects.create(profile=cls.profile, company="Sample Studio", title="Intern", description="Built accessible forms.")
        ProfessionalLink.objects.create(profile=cls.profile, label="Portfolio", url="https://example.com/portfolio")

    def setUp(self):
        self.list_url = reverse("jobs:my_applications")
        self.applicants_url = reverse("jobs:job_applications", args=[self.job.pk])
        self.detail_url = reverse("jobs:application_detail", args=[self.application.pk])
        self.status_url = reverse("jobs:application_status", args=[self.application.pk])

    def test_new_applications_default_to_applied_and_ignore_posted_status(self):
        self.client.force_login(self.other_seeker)
        self.client.post(reverse("jobs:apply", args=[self.job.pk]), {"status": "offer"})
        application = Application.objects.get(job=self.job, applicant=self.other_seeker)
        self.assertEqual(application.status, Application.Status.APPLIED)

    def test_seeker_sees_only_their_own_applications(self):
        self.client.force_login(self.seeker)
        response = self.client.get(self.list_url)
        self.assertQuerySetEqual(response.context["applications"], [self.application])
        self.assertContains(response, "My tailored note")
        self.assertContains(response, "Applied")
        self.assertNotContains(response, "Another private note")

    def test_empty_application_list(self):
        Application.objects.filter(applicant=self.seeker).delete()
        self.client.force_login(self.seeker)
        response = self.client.get(self.list_url)
        self.assertContains(response, "No applications yet")
        self.assertContains(response, reverse("jobs:search"))

    def test_all_stages_are_saved_and_visible_to_candidate(self):
        for stage, label in Application.Status.choices:
            with self.subTest(stage=stage):
                self.client.force_login(self.recruiter)
                response = self.client.post(self.status_url, {"status": stage}, follow=True)
                self.assertRedirects(response, self.detail_url)
                self.application.refresh_from_db()
                self.assertEqual(self.application.status, stage)
                self.client.force_login(self.seeker)
                response = self.client.get(self.list_url)
                self.assertEqual(response.context["applications"][0].status, stage)
                self.assertContains(response, f'<span class="badge">{label}</span>', html=True)
                self.assertContains(self.client.get(reverse("jobs:detail", args=[self.job.pk])), f'<span class="badge">{label}</span>', html=True)

    def test_recruiter_sees_complete_profile_and_application_together(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(self.detail_url)
        for text in ("candidate", "Engineer", "My tailored note", "Django developer", "Python, SQL", "Atlanta", "Example University", "Computer Science", "Sample Studio", "Intern", "Built accessible forms.", "https://example.com/portfolio", "Portfolio"):
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertNotContains(response, "Another private note")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_missing_profile_and_optional_sections_have_empty_states(self):
        self.client.force_login(self.recruiter)
        self.profile.delete()
        response = self.client.get(self.detail_url)
        self.assertContains(response, "has not created a profile")
        self.assertContains(response, "My tailored note")
        JobSeekerProfile.objects.create(user=self.seeker)
        response = self.client.get(self.detail_url)
        for text in ("No skills provided", "No education provided", "No work experience provided", "No professional links provided"):
            self.assertContains(response, text)

    def test_recruiter_list_is_scoped_to_selected_job(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(self.applicants_url)
        self.assertQuerySetEqual(response.context["applications"], [self.application])
        self.assertContains(response, self.detail_url)
        self.assertNotContains(response, "other-candidate")
        Application.objects.filter(job=self.job).delete()
        self.assertContains(self.client.get(self.applicants_url), "No applications yet")

    def test_other_recruiter_cannot_read_or_update_applications(self):
        self.client.force_login(self.other_recruiter)
        for url in (self.applicants_url, self.detail_url):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(self.status_url, {"status": "offer"}).status_code, 404)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.APPLIED)

    def test_other_roles_cannot_use_recruiter_endpoints(self):
        for user in (self.seeker, self.other_seeker, self.admin):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.applicants_url).status_code, 403)
                self.assertEqual(self.client.get(self.detail_url).status_code, 403)
                self.assertEqual(self.client.post(self.status_url, {"status": "offer"}).status_code, 403)
        for user in (self.recruiter, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_anonymous_access_requires_login(self):
        for url in (self.list_url, self.applicants_url, self.detail_url):
            self.assertRedirects(self.client.get(url), f'{reverse("accounts:login")}?next={url}')
        self.assertRedirects(self.client.post(self.status_url, {"status": "offer"}), f'{reverse("accounts:login")}?next={self.status_url}')

    def test_invalid_status_and_get_requests_do_not_change_record(self):
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(self.status_url).status_code, 405)
        for value in ("invalid", "", "Offer"):
            response = self.client.post(self.status_url, {"status": value})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["status_form"].errors)
            self.application.refresh_from_db()
            self.assertEqual(self.application.status, Application.Status.APPLIED)

    def test_status_update_cannot_change_note_or_relationships(self):
        self.client.force_login(self.recruiter)
        self.client.post(self.status_url, {"status": "review", "note": "Overwrite", "applicant": self.other_seeker.pk, "job": self.other_job.pk})
        self.application.refresh_from_db()
        self.assertEqual(self.application.note, "My tailored note")
        self.assertEqual(self.application.applicant, self.seeker)
        self.assertEqual(self.application.job, self.job)

    def test_csrf_is_required_for_status_updates(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.recruiter)
        self.assertEqual(client.post(self.status_url, {"status": "review"}).status_code, 403)
        client.get(self.detail_url)
        response = client.post(self.status_url, {"status": "review", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertRedirects(response, self.detail_url)

    def test_removed_job_keeps_application_access_but_hides_job_link_from_seeker(self):
        self.job.status = Job.Status.REMOVED
        self.job.save()
        self.client.force_login(self.seeker)
        response = self.client.get(self.list_url)
        self.assertContains(response, "My tailored note")
        self.assertNotContains(response, f'href="{reverse("jobs:detail", args=[self.job.pk])}"')
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(self.applicants_url).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        self.assertRedirects(self.client.post(self.status_url, {"status": "closed"}), self.detail_url)

    def test_profile_content_is_escaped_and_unsafe_links_are_not_clickable(self):
        self.profile.headline = '<script>alert("profile")</script>'
        self.profile.save()
        ProfessionalLink.objects.create(profile=self.profile, label="Unsafe", url="javascript:alert(1)")
        self.client.force_login(self.recruiter)
        response = self.client.get(self.detail_url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")
        self.assertNotContains(response, 'href="javascript:')

    def test_workspace_navigation_reaches_new_features(self):
        self.client.force_login(self.seeker)
        self.assertContains(self.client.get(reverse("accounts:job_seeker_area")), self.list_url)
        self.client.force_login(self.recruiter)
        self.assertContains(self.client.get(reverse("accounts:recruiter_area")), reverse("jobs:mine"))
        self.assertContains(self.client.get(reverse("jobs:mine")), self.applicants_url)
        self.assertContains(self.client.get(reverse("jobs:detail", args=[self.job.pk])), self.applicants_url)

    def test_missing_application_returns_404(self):
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(reverse("jobs:application_detail", args=[999999])).status_code, 404)
        self.assertEqual(self.client.post(reverse("jobs:application_status", args=[999999]), {"status": "review"}).status_code, 404)

    def test_profile_record_changes_flow_through_to_recruiter_review(self):
        cases = (
            ("education", Education, {"institution": "New University", "degree": "MS"}, "institution", "Updated University"),
            ("work_experience", WorkExperience, {"company": "New Company", "title": "Engineer"}, "company", "Updated Company"),
            ("professional_link", ProfessionalLink, {"label": "New Portfolio", "url": "https://example.com/new"}, "label", "Updated Portfolio"),
        )
        for route, model, data, field, updated_value in cases:
            with self.subTest(record=route):
                self.client.force_login(self.seeker)
                response = self.client.post(reverse(f"accounts:add_{route}"), data)
                self.assertRedirects(response, reverse("accounts:job_seeker_area"))
                record = model.objects.get(profile=self.profile, **{field: data[field]})
                self.client.force_login(self.recruiter)
                self.assertContains(self.client.get(self.detail_url), data[field])

                self.client.force_login(self.seeker)
                updated_data = {**data, field: updated_value}
                response = self.client.post(reverse(f"accounts:edit_{route}", args=[record.pk]), updated_data)
                self.assertRedirects(response, reverse("accounts:job_seeker_area"))
                self.client.force_login(self.recruiter)
                self.assertContains(self.client.get(self.detail_url), updated_value)

                self.client.force_login(self.seeker)
                response = self.client.post(reverse(f"accounts:delete_{route}", args=[record.pk]))
                self.assertRedirects(response, reverse("accounts:job_seeker_area"))
                self.client.force_login(self.recruiter)
                response = self.client.get(self.detail_url)
                self.assertNotContains(response, updated_value)
                self.assertContains(response, "My tailored note")
