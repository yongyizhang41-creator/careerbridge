import csv
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from jobs.models import Application, Job

from .decorators import role_required
from .forms import (
    EducationForm,
    JobSeekerProfileForm,
    RegistrationForm,
    WorkExperienceForm,
    ProfessionalLinkForm,
    ProjectForm,
    CandidateSearchForm,
    SavedSearchForm,
)
from .models import (
    Education,
    JobSeekerProfile,
    ProfessionalLink,
    User,
    WorkExperience,
    Project,
    SavedSearch,
)


def register(request):
    form = RegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:registration_complete")

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )


def registration_complete(request):
    return render(request, "accounts/registration_complete.html")


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html")


@role_required(User.Role.JOB_SEEKER)
def job_seeker_area(request):
    profile = JobSeekerProfile.objects.filter(user=request.user).first()

    if profile:
        education_records = profile.education_records.all()
        work_experiences = profile.work_experiences.all()
        professional_links = profile.professional_links.all()
        projects = profile.projects.all()
    else:
        education_records = Education.objects.none()
        work_experiences = WorkExperience.objects.none()
        professional_links = ProfessionalLink.objects.none()
        projects = Project.objects.none()

    return render(
        request,
        "accounts/job_seeker_area.html",
        {
            "profile": profile,
            "education_records": education_records,
            "work_experiences": work_experiences,
            "professional_links": professional_links,
            "projects": projects,
        },
    )


@role_required(User.Role.JOB_SEEKER)
def edit_job_seeker_profile(request):
    profile = JobSeekerProfile.objects.filter(user=request.user).first()

    form = JobSeekerProfileForm(
        request.POST or None,
        instance=profile,
    )

    if request.method == "POST" and form.is_valid():
        profile = form.save(commit=False)
        profile.user = request.user
        profile.save()

        messages.success(request, "Your profile has been saved.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/profile_form.html",
        {"form": form},
    )


@role_required(User.Role.RECRUITER)
def recruiter_area(request):
    new_matches = sum(
        _new_matches(saved).count() for saved in request.user.saved_searches.all()
    )
    return render(
        request,
        "accounts/recruiter_area.html",
        {"new_matches": new_matches},
    )


@role_required(User.Role.ADMINISTRATOR)
def reporting(request):
    """Show administrators a privacy-conscious summary of account usage."""
    account_counts = User.objects.aggregate(
        total=Count("id"),
        job_seekers=Count(
            "id",
            filter=Q(role=User.Role.JOB_SEEKER),
        ),
        recruiters=Count(
            "id",
            filter=Q(role=User.Role.RECRUITER),
        ),
        administrators=Count(
            "id",
            filter=Q(role=User.Role.ADMINISTRATOR),
        ),
    )
    job_counts = Job.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=Job.Status.ACTIVE)),
        removed=Count("id", filter=Q(status=Job.Status.REMOVED)),
    )
    return render(
        request,
        "accounts/reporting.html",
        {
            "account_counts": account_counts,
            "job_counts": job_counts,
            "application_count": Application.objects.count(),
        },
    )


def _spreadsheet_safe(value):
    """Prevent text cells from being interpreted as spreadsheet formulas."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def _csv_datetime(value):
    """Return a stable, timezone-aware ISO 8601 string for CSV output."""
    if value is None:
        return ""
    return value.isoformat()


@role_required(User.Role.ADMINISTRATOR)
def export_users_csv(request):
    """Download a minimal account-usage dataset for administrator reporting."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = (
        f"careerbridge-user-report-{timezone.localdate().isoformat()}.csv"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response, lineterminator="\n")
    writer.writerow(
        [
            "user_id",
            "username",
            "role",
            "is_active",
            "date_joined",
            "last_login",
        ]
    )

    users = User.objects.order_by("id").iterator()
    for user in users:
        writer.writerow(
            [
                user.pk,
                _spreadsheet_safe(user.username),
                user.role,
                user.is_active,
                _csv_datetime(user.date_joined),
                _csv_datetime(user.last_login),
            ]
        )

    return response


@role_required(User.Role.ADMINISTRATOR)
def export_jobs_csv(request):
    """Download job-post activity without exposing application content."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"careerbridge-job-report-{timezone.localdate().isoformat()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response, lineterminator="\n")
    writer.writerow(
        [
            "job_id",
            "title",
            "company",
            "recruiter_username",
            "remote_type",
            "status",
            "created_at",
        ]
    )
    jobs = Job.objects.select_related("recruiter").order_by("id").iterator()
    for job in jobs:
        writer.writerow(
            [
                job.pk,
                _spreadsheet_safe(job.title),
                _spreadsheet_safe(job.company),
                _spreadsheet_safe(job.recruiter.username),
                job.remote_type,
                job.status,
                _csv_datetime(job.created_at),
            ]
        )

    return response


@role_required(User.Role.ADMINISTRATOR)
def export_applications_csv(request):
    """Download application activity while excluding private applicant notes."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = (
        f"careerbridge-application-report-{timezone.localdate().isoformat()}.csv"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response, lineterminator="\n")
    writer.writerow(
        [
            "application_id",
            "job_id",
            "job_title",
            "company",
            "applicant_username",
            "created_at",
        ]
    )
    applications = (
        Application.objects.select_related("job", "applicant")
        .order_by("id")
        .iterator()
    )
    for application in applications:
        writer.writerow(
            [
                application.pk,
                application.job_id,
                _spreadsheet_safe(application.job.title),
                _spreadsheet_safe(application.job.company),
                _spreadsheet_safe(application.applicant.username),
                _csv_datetime(application.created_at),
            ]
        )

    return response


@role_required(User.Role.JOB_SEEKER)
def add_education(request):
    profile = JobSeekerProfile.objects.filter(user=request.user).first()

    if profile is None:
        messages.info(request, "Create your profile before adding education.")
        return redirect("accounts:edit_job_seeker_profile")

    form = EducationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        education = form.save(commit=False)
        education.profile = profile
        education.save()

        messages.success(request, "Education record added.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/education_form.html",
        {"form": form, "is_editing": False},
    )


@role_required(User.Role.JOB_SEEKER)
def edit_education(request, pk):
    education = get_object_or_404(
        Education,
        pk=pk,
        profile__user=request.user,
    )
    form = EducationForm(request.POST or None, instance=education)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Education record updated.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/education_form.html",
        {"form": form, "is_editing": True},
    )


@role_required(User.Role.JOB_SEEKER)
@require_POST
def delete_education(request, pk):
    education = get_object_or_404(
        Education,
        pk=pk,
        profile__user=request.user,
    )
    education.delete()
    messages.success(request, "Education record deleted.")
    return redirect("accounts:job_seeker_area")


@role_required(User.Role.JOB_SEEKER)
def add_work_experience(request):
    profile = JobSeekerProfile.objects.filter(user=request.user).first()

    if profile is None:
        messages.info(
            request,
            "Create your profile before adding work experience.",
        )
        return redirect("accounts:edit_job_seeker_profile")

    form = WorkExperienceForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        work_experience = form.save(commit=False)
        work_experience.profile = profile
        work_experience.save()

        messages.success(request, "Work experience added.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/work_experience_form.html",
        {"form": form, "is_editing": False},
    )


@role_required(User.Role.JOB_SEEKER)
def edit_work_experience(request, pk):
    work_experience = get_object_or_404(
        WorkExperience,
        pk=pk,
        profile__user=request.user,
    )
    form = WorkExperienceForm(request.POST or None, instance=work_experience)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Work experience updated.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/work_experience_form.html",
        {"form": form, "is_editing": True},
    )


@role_required(User.Role.JOB_SEEKER)
@require_POST
def delete_work_experience(request, pk):
    work_experience = get_object_or_404(
        WorkExperience,
        pk=pk,
        profile__user=request.user,
    )
    work_experience.delete()
    messages.success(request, "Work experience deleted.")
    return redirect("accounts:job_seeker_area")

@role_required(User.Role.JOB_SEEKER)
def add_professional_link(request):
    profile = JobSeekerProfile.objects.filter(user=request.user).first()

    if profile is None:
        messages.info(
            request,
            "Create your profile before adding professional links.",
        )
        return redirect("accounts:edit_job_seeker_profile")

    form = ProfessionalLinkForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        professional_link = form.save(commit=False)
        professional_link.profile = profile
        professional_link.save()

        messages.success(request, "Professional link added.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/professional_link_form.html",
        {"form": form, "is_editing": False},
    )


@role_required(User.Role.JOB_SEEKER)
def edit_professional_link(request, pk):
    professional_link = get_object_or_404(
        ProfessionalLink,
        pk=pk,
        profile__user=request.user,
    )
    form = ProfessionalLinkForm(request.POST or None, instance=professional_link)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Professional link updated.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/professional_link_form.html",
        {"form": form, "is_editing": True},
    )


@role_required(User.Role.JOB_SEEKER)
@require_POST
def delete_professional_link(request, pk):
    professional_link = get_object_or_404(
        ProfessionalLink,
        pk=pk,
        profile__user=request.user,
    )
    professional_link.delete()
    messages.success(request, "Professional link deleted.")
    return redirect("accounts:job_seeker_area")

@role_required(User.Role.JOB_SEEKER)
def add_project(request):
    profile = JobSeekerProfile.objects.filter(user=request.user).first()

    if profile is None:
        messages.info(request, "Create your profile before adding projects.")
        return redirect("accounts:edit_job_seeker_profile")

    form = ProjectForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.profile = profile
        project.save()

        messages.success(request, "Project added.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/project_form.html",
        {"form": form, "is_editing": False},
    )


@role_required(User.Role.JOB_SEEKER)
def edit_project(request, pk):
    project = get_object_or_404(Project, pk=pk, profile__user=request.user)
    form = ProjectForm(request.POST or None, instance=project)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Project updated.")
        return redirect("accounts:job_seeker_area")

    return render(
        request,
        "accounts/project_form.html",
        {"form": form, "is_editing": True},
    )


@role_required(User.Role.JOB_SEEKER)
@require_POST
def delete_project(request, pk):
    project = get_object_or_404(Project, pk=pk, profile__user=request.user)
    project.delete()
    messages.success(request, "Project deleted.")
    return redirect("accounts:job_seeker_area")
def _searchable_profiles():
    """Profiles recruiters may find: active job seekers who opted in to recruiter visibility (US5)."""
    return JobSeekerProfile.objects.filter(
        user__role=User.Role.JOB_SEEKER,
        user__is_active=True,
        recruiter_visible=True,
    )


def _filter_candidates(form, profiles):
    if not form.is_valid():
        return profiles.none() if form.is_bound else profiles

    data = form.cleaned_data

    for skill in data["skills"].split(","):
        skill = skill.strip()
        if skill:
            pattern = r"(^|,)\s*" + re.escape(skill) + r"\s*(,|$)"
            profiles = profiles.filter(skills__iregex=pattern)

    if data["location"]:
        profiles = profiles.filter(location__icontains=data["location"])

    if data["project"]:
        keyword = data["project"].strip()
        profiles = profiles.filter(
            Q(projects__title__icontains=keyword)
            | Q(projects__description__icontains=keyword)
        ).distinct()

    return profiles


@role_required(User.Role.RECRUITER)
def candidate_search(request):
    form = CandidateSearchForm(request.GET or None)
    profiles = (
        _filter_candidates(form, _searchable_profiles())
        .select_related("user")
        .prefetch_related("projects")
        .order_by("user__username")
    )
    return render(
        request,
        "accounts/candidate_search.html",
        {"form": form, "profiles": profiles},
    )
    
    
def _saved_search_matches(saved):
    form = CandidateSearchForm(saved.criteria())
    return _filter_candidates(form, _searchable_profiles())


def _new_matches(saved):
    return _saved_search_matches(saved).exclude(pk__in=saved.seen_profiles.all())


@role_required(User.Role.RECRUITER)
@require_POST
def save_candidate_search(request):
    form = SavedSearchForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Give the search a name and at least one filter.")
        return redirect("accounts:candidate_search")

    saved = form.save(commit=False)
    saved.recruiter = request.user
    saved.save()
    saved.seen_profiles.set(_saved_search_matches(saved))

    messages.success(request, "Search saved. New matching candidates will be flagged here.")
    return redirect("accounts:saved_searches")


@role_required(User.Role.RECRUITER)
def saved_searches(request):
    searches = list(request.user.saved_searches.all())
    for saved in searches:
        saved.total_count = _saved_search_matches(saved).count()
        saved.new_count = _new_matches(saved).count()

    return render(
        request,
        "accounts/saved_searches.html",
        {"searches": searches},
    )


@role_required(User.Role.RECRUITER)
def saved_search_detail(request, pk):
    saved = get_object_or_404(SavedSearch, pk=pk, recruiter=request.user)
    new_ids = set(_new_matches(saved).values_list("pk", flat=True))
    profiles = (
        _saved_search_matches(saved)
        .select_related("user")
        .prefetch_related("projects")
        .order_by("user__username")
    )
    saved.seen_profiles.add(*profiles)

    return render(
        request,
        "accounts/candidate_search.html",
        {
            "form": CandidateSearchForm(saved.criteria()),
            "profiles": profiles,
            "new_ids": new_ids,
            "saved_search": saved,
        },
    )


@role_required(User.Role.RECRUITER)
@require_POST
def delete_saved_search(request, pk):
    saved = get_object_or_404(SavedSearch, pk=pk, recruiter=request.user)
    saved.delete()
    messages.success(request, "Saved search deleted.")
    return redirect("accounts:saved_searches")
