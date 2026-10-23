from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from .models import Application, CartItem, Job


class WorkflowTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seeker = User.objects.create_user(username="cart-seeker", role=User.Role.JOB_SEEKER)
        cls.other_seeker = User.objects.create_user(username="other-cart-seeker", role=User.Role.JOB_SEEKER)
        cls.recruiter = User.objects.create_user(username="pipeline-owner", role=User.Role.RECRUITER)
        cls.other_recruiter = User.objects.create_user(username="other-owner", role=User.Role.RECRUITER)
        cls.admin = User.objects.create_user(username="workflow-admin", role=User.Role.ADMINISTRATOR)
        cls.job = Job.objects.create(recruiter=cls.recruiter, title="Python Engineer", company="First", description="First job description", salary_min=0, salary_max=90000, skills="Python, Django", remote_type="remote", visa_sponsorship=True)
        cls.second_job = Job.objects.create(recruiter=cls.recruiter, title="SQL Engineer", company="Second", description="Second job description", salary_min=70000, salary_max=110000, address="Atlanta", remote_type="hybrid")
        cls.other_job = Job.objects.create(recruiter=cls.other_recruiter, title="Other job", company="Other", description="Private other application")


class JobCartTests(WorkflowTestCase):
    def setUp(self):
        self.client.force_login(self.seeker)
        self.cart_url = reverse("jobs:cart")
        self.add_url = reverse("jobs:cart_add", args=[self.job.pk])

    def test_empty_cart_and_add_does_not_apply(self):
        self.assertContains(self.client.get(self.cart_url), "Your cart is empty")
        self.assertRedirects(self.client.post(self.add_url), self.cart_url)
        item = CartItem.objects.get()
        self.assertEqual(item.owner, self.seeker)
        self.assertEqual(item.job, self.job)
        self.assertFalse(Application.objects.exists())
        self.assertContains(self.client.get(self.cart_url), "Python Engineer")

    def test_duplicate_add_is_idempotent_and_database_enforces_uniqueness(self):
        self.client.post(self.add_url)
        self.client.post(self.add_url)
        self.assertEqual(CartItem.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(owner=self.seeker, job=self.job)

    def test_cart_survives_new_session_and_isolated_by_account(self):
        self.client.post(self.add_url)
        self.client.logout()
        self.client.force_login(self.seeker)
        self.assertContains(self.client.get(self.cart_url), "Python Engineer")
        self.client.force_login(self.other_seeker)
        self.assertContains(self.client.get(self.cart_url), "Your cart is empty")
        self.client.post(self.add_url)
        self.assertEqual(CartItem.objects.count(), 2)

    def test_remove_only_own_item_and_does_not_remove_application(self):
        item = CartItem.objects.create(owner=self.seeker, job=self.job)
        application = Application.objects.create(applicant=self.seeker, job=self.job)
        url = reverse("jobs:cart_remove", args=[item.pk])
        self.client.force_login(self.other_seeker)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.seeker)
        self.assertRedirects(self.client.post(url), self.cart_url)
        self.assertFalse(CartItem.objects.exists())
        self.assertTrue(Application.objects.filter(pk=application.pk).exists())

    def test_selected_jobs_compare_all_relevant_details(self):
        first = CartItem.objects.create(owner=self.seeker, job=self.job)
        second = CartItem.objects.create(owner=self.seeker, job=self.second_job)
        Application.objects.create(applicant=self.seeker, job=self.job, note="My note")
        response = self.client.get(reverse("jobs:cart_compare"), {"items": [first.pk, second.pk]})
        self.assertTemplateUsed(response, "jobs/cart_compare.html")
        for text in ("Python Engineer", "SQL Engineer", "First job description", "Second job description", "Python, Django", "Remote", "Hybrid", "Atlanta", "90000", "110000", "Available", "Not offered", "Already applied"):
            self.assertContains(response, text)
        self.assertContains(response, reverse("jobs:detail", args=[self.second_job.pk]))
        self.assertEqual(Application.objects.count(), 1)

    def test_comparison_rejects_missing_one_duplicate_or_foreign_items(self):
        item = CartItem.objects.create(owner=self.seeker, job=self.job)
        other = CartItem.objects.create(owner=self.other_seeker, job=self.other_job)
        for ids in ([], [item.pk], [item.pk, item.pk], [item.pk, other.pk], [item.pk, 999999]):
            with self.subTest(ids=ids):
                response = self.client.get(reverse("jobs:cart_compare"), {"items": ids})
                self.assertTemplateUsed(response, "jobs/cart.html")
                self.assertTrue(response.context["comparison_form"].errors)
                self.assertNotContains(response, "Private other application")

    def test_removed_jobs_cannot_be_saved_or_compared(self):
        item = CartItem.objects.create(owner=self.seeker, job=self.job)
        second = CartItem.objects.create(owner=self.seeker, job=self.second_job)
        self.job.status = Job.Status.REMOVED
        self.job.save()
        self.assertEqual(self.client.post(self.add_url).status_code, 404)
        response = self.client.get(self.cart_url)
        self.assertContains(response, "no longer available")
        self.assertNotContains(response, "First job description")
        response = self.client.get(reverse("jobs:cart_compare"), {"items": [item.pk, second.pk]})
        self.assertTrue(response.context["comparison_form"].errors)
        self.assertNotContains(response, "First job description")
        self.assertRedirects(self.client.post(reverse("jobs:cart_remove", args=[item.pk])), self.cart_url)

    def test_read_only_requests_do_not_mutate_and_csrf_is_required(self):
        self.assertEqual(self.client.get(self.add_url).status_code, 405)
        item = CartItem.objects.create(owner=self.seeker, job=self.job)
        remove_url = reverse("jobs:cart_remove", args=[item.pk])
        self.assertEqual(self.client.get(remove_url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.seeker)
        self.assertEqual(client.post(self.add_url).status_code, 403)
        self.assertEqual(client.post(remove_url).status_code, 403)

    def test_cart_endpoints_require_seeker_role(self):
        urls = [self.cart_url, self.add_url, reverse("jobs:cart_compare"), reverse("jobs:cart_remove", args=[1])]
        for user in (self.recruiter, self.admin):
            self.client.force_login(user)
            for url in urls:
                response = self.client.post(url) if '/add/' in url or '/remove/' in url else self.client.get(url)
                self.assertEqual(response.status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.cart_url).status_code, 302)

    def test_cart_apply_uses_existing_form_and_keeps_cart(self):
        self.client.post(self.add_url)
        self.client.post(reverse("jobs:apply", args=[self.job.pk]), {"note": "A tailored cart application"})
        self.assertEqual(Application.objects.get().note, "A tailored cart application")
        self.assertEqual(CartItem.objects.count(), 1)
        self.assertContains(self.client.get(self.cart_url), "Already applied")


class HiringPipelineTests(WorkflowTestCase):
    def setUp(self):
        self.application = Application.objects.create(job=self.job, applicant=self.seeker, note="Original note")
        self.other_application = Application.objects.create(job=self.other_job, applicant=self.other_seeker)
        self.url = reverse("jobs:pipeline")
        self.move_url = reverse("jobs:pipeline_move", args=[self.application.pk])
        self.client.force_login(self.recruiter)

    def test_board_groups_owned_applications_into_five_stages(self):
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["columns"]), 5)
        self.assertEqual(response.context["columns"][0]["applications"], [self.application])
        self.assertContains(response, "cart-seeker")
        self.assertNotContains(response, "other-cart-seeker")
        self.assertContains(response, reverse("jobs:application_detail", args=[self.application.pk]))

    def test_applicant_list_keeps_map_and_pipeline_entry_points(self):
        response = self.client.get(reverse("jobs:job_applications", args=[self.job.pk]))
        self.assertContains(response, reverse("jobs:applicant_map", args=[self.job.pk]))
        self.assertContains(response, reverse("jobs:pipeline") + f"?job={self.job.pk}")
        self.assertContains(response, "Message candidate")

    def test_job_filter_is_owned_and_does_not_expose_other_jobs(self):
        self.assertEqual(self.client.get(self.url, {"job": self.other_job.pk}).status_code, 404)
        self.assertEqual(self.client.get(self.url, {"job": "invalid"}).status_code, 404)
        response = self.client.get(self.url, {"job": self.second_job.pk})
        self.assertTrue(all(not column["applications"] for column in response.context["columns"]))

    def test_every_stage_updates_candidate_tracking_without_changing_note(self):
        previous = Application.Status.APPLIED
        for value, label in Application.Status.choices:
            response = self.client.post(self.move_url, {"status": value, "expected_status": previous}, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], value)
            self.application.refresh_from_db()
            self.assertEqual(self.application.note, "Original note")
            candidate = Client()
            candidate.force_login(self.seeker)
            self.assertContains(candidate.get(reverse("jobs:my_applications")), f'<span class="badge">{label}</span>', html=True)
            previous = value

    def test_stale_move_cannot_overwrite_new_status(self):
        self.application.status = Application.Status.INTERVIEW
        self.application.save()
        response = self.client.post(self.move_url, {"status": "review", "expected_status": "applied"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 409)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.INTERVIEW)

    def test_invalid_move_is_rejected_without_mutation(self):
        for data in ({"status": "invalid", "expected_status": "applied"}, {"status": "offer"}):
            response = self.client.post(self.move_url, data, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.application.refresh_from_db()
            self.assertEqual(self.application.status, Application.Status.APPLIED)

    def test_plain_form_works_without_javascript_and_preserves_filter(self):
        response = self.client.post(self.move_url, {"status": "review", "expected_status": "applied", "job": self.job.pk})
        self.assertRedirects(response, self.url + f"?job={self.job.pk}")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.REVIEW)

    def test_original_status_editor_still_updates_pipeline(self):
        self.client.post(reverse("jobs:application_status", args=[self.application.pk]), {"status": "offer"})
        response = self.client.get(self.url)
        self.assertEqual(response.context["columns"][3]["applications"][0].pk, self.application.pk)

    def test_unauthorized_or_get_requests_cannot_move(self):
        self.assertEqual(self.client.get(self.move_url).status_code, 405)
        self.client.force_login(self.other_recruiter)
        self.assertEqual(self.client.post(self.move_url, {"status": "offer", "expected_status": "applied"}).status_code, 404)
        for user in (self.seeker, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.move_url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.recruiter)
        self.assertEqual(client.post(self.move_url, {"status": "review", "expected_status": "applied"}).status_code, 403)
        client.get(self.url)
        response = client.post(self.move_url, {"status": "review", "expected_status": "applied", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)

    def test_removed_jobs_keep_their_pipeline(self):
        self.job.status = Job.Status.REMOVED
        self.job.save()
        self.assertContains(self.client.get(self.url, {"job": self.job.pk}), "cart-seeker")
        self.assertEqual(self.client.post(self.move_url, {"status": "closed", "expected_status": "applied"}, HTTP_ACCEPT="application/json").status_code, 200)
