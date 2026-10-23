import re
from collections import Counter
from accounts.permissions import can_view_profile
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from .recommendations import recommend_candidates, recommend_jobs
from accounts.decorators import role_required
from accounts.models import JobSeekerProfile, User
from .forms import (
    ApplicationForm,
    ApplicationStatusForm,
    CommuteRadiusForm,
    JobForm,
    JobSearchForm,
)
from .models import Application, Job

recruiter_required = role_required(User.Role.RECRUITER)
admin_required = role_required(User.Role.ADMINISTRATOR)

@recruiter_required
def candidate_recommendations(request, pk):
    job = get_object_or_404(
        Job,
        pk=pk,
        recruiter=request.user,
        status=Job.Status.ACTIVE,
    )
    return render(
        request,
        "jobs/candidate_recommendations.html",
        {
            "job": job,
            "recommendations": recommend_candidates(request.user, job),
            "has_skills": bool(job.skill_list()),
        },
    )


@recruiter_required
def candidate_profile(request, pk, profile_pk):
    job = get_object_or_404(
        Job,
        pk=pk,
        recruiter=request.user,
        status=Job.Status.ACTIVE,
    )
    profile = get_object_or_404(
        JobSeekerProfile.objects.select_related("user"),
        pk=profile_pk,
        user__role=User.Role.JOB_SEEKER,
        user__is_active=True,
    )

    if not can_view_profile(request.user, profile):
        raise Http404

    return render(
        request,
        "jobs/candidate_profile.html",
        {"job": job, "profile": profile},
    )



@role_required(User.Role.JOB_SEEKER)
def job_recommendations(request):
    profile = JobSeekerProfile.objects.filter(user=request.user).first()
    has_skills = bool(profile and profile.skill_list())

    return render(
        request,
        "jobs/job_recommendations.html",
        {
            "recommendations": recommend_jobs(request.user),
            "has_skills": has_skills,
        },
    )


@role_required(User.Role.JOB_SEEKER)
def my_applications(request):
    applications = (
        Application.objects.filter(applicant=request.user)
        .select_related("job")
        .order_by("-created_at", "-pk")
    )
    return render(request, "jobs/my_applications.html", {"applications": applications})


@recruiter_required
def applicant_map(request, pk):
    """Show the recruiter where this job's applicants are based (US19)."""
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    applications = job.applications.select_related("applicant__job_seeker_profile")
    points = []
    places = Counter()
    for application in applications:
        profile = getattr(application.applicant, "job_seeker_profile", None)
        location = profile.location.strip() if profile else ""
        places[location or "Location not given"] += 1
        if profile and profile.lat is not None and profile.lng is not None:
            points.append({
                "name": application.applicant.get_full_name() or application.applicant.username,
                "location": location,
                "status": application.get_status_display(),
                "lat": profile.lat,
                "lng": profile.lng,
                "url": reverse("jobs:application_detail", args=[application.pk]),
            })
    return render(request, "jobs/applicant_map.html", {
        "job": job,
        "points": points,
        "total": len(applications),
        "places": places.most_common(),
    })


@recruiter_required
def job_applications(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    applications = job.applications.select_related("applicant").order_by("-created_at", "-pk")
    return render(request, "jobs/job_applications.html", {
        "job": job, "applications": applications,
    })


def _application_review_context(viewer, application, status_form):
    profile = JobSeekerProfile.objects.filter(
        user=application.applicant,
    ).first()

    if not can_view_profile(viewer, profile):
        profile = None

    return {
        "application": application,
        "profile": profile,
        "status_form": status_form,
    }


@recruiter_required
def application_detail(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("job", "applicant"),
        pk=pk, job__recruiter=request.user,
    )
    return render(
        request,
        "jobs/application_detail.html",
        _application_review_context(
            request.user,
            application,
            ApplicationStatusForm(instance=application),
        ),
    )


@recruiter_required
@require_POST
def application_status(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("job", "applicant"),
        pk=pk, job__recruiter=request.user,
    )
    form = ApplicationStatusForm(request.POST, instance=application)
    if form.is_valid():
        # Only update the stage; never overwrite the applicant's submitted note.
        application.status = form.cleaned_data["status"]
        application.save(update_fields=["status"])
        messages.success(request, "Application status updated.")
        return redirect("jobs:application_detail", pk=application.pk)
    return render(
        request,
        "jobs/application_detail.html",
        _application_review_context(request.user, application, form),
    )


@recruiter_required
def job_create(request):
    if request.method == "POST":
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.recruiter = request.user
            job.save()
            return redirect("jobs:detail", pk=job.pk)
    else:
        form = JobForm()
    return render(request, "jobs/job_form.html", {"form": form, "job": None})


@recruiter_required
def job_edit(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    if request.method == "POST":
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            return redirect("jobs:detail", pk=job.pk)
    else:
        form = JobForm(instance=job)
    return render(request, "jobs/job_form.html", {"form": form, "job": job})


@recruiter_required
def my_jobs(request):
    jobs = request.user.jobs.all()
    return render(request, "jobs/my_jobs.html", {"jobs": jobs})


def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)
    if job.status == Job.Status.REMOVED:
        user = request.user
        can_see = user.is_authenticated and (
            user == job.recruiter or user.role == User.Role.ADMINISTRATOR
        )
        if not can_see:
            raise Http404

    application = None
    if request.user.is_authenticated and request.user.role == User.Role.JOB_SEEKER:
        application = Application.objects.filter(job=job, applicant=request.user).first()
    return render(request, "jobs/job_detail.html", {
        "job": job,
        "application": application,
        "application_form": ApplicationForm(),
    })


@role_required(User.Role.JOB_SEEKER)
@require_POST
def job_apply(request, pk):
    job = get_object_or_404(Job, pk=pk, status=Job.Status.ACTIVE)
    if Application.objects.filter(job=job, applicant=request.user).exists():
        messages.info(request, "You have already applied to this job.")
        return redirect("jobs:detail", pk=job.pk)

    form = ApplicationForm(request.POST)
    if not form.is_valid():
        return render(request, "jobs/job_detail.html", {
            "job": job,
            "application_form": form,
        })

    # The database constraint also protects against simultaneous submissions.
    application, created = Application.objects.get_or_create(
        job=job, applicant=request.user, defaults={"note": form.cleaned_data["note"]}
    )
    if created:
        messages.success(request, "Your application has been submitted.")
    else:
        messages.info(request, "You have already applied to this job.")
    return redirect("jobs:detail", pk=job.pk)

def _filter_jobs(form, jobs):
    """Apply JobSearchForm filters; shared by the search page and the job map."""
    if not form.is_valid():
        return jobs.none() if form.is_bound else jobs

    data = form.cleaned_data

    if data["title"]:
        jobs = jobs.filter(title__icontains=data["title"])

    for skill in data["skills"].split(","):
        skill = skill.strip()
        if skill:
            pattern = r"(^|,)\s*" + re.escape(skill) + r"\s*(,|$)"
            jobs = jobs.filter(skills__iregex=pattern)

    if data["location"]:
        jobs = jobs.filter(address__icontains=data["location"])

    lo, hi = data["salary_min"], data["salary_max"]
    if lo is not None:
        jobs = jobs.filter(
            Q(salary_max__gte=lo) | Q(salary_max__isnull=True, salary_min__isnull=False)
        )
    if hi is not None:
        jobs = jobs.filter(
            Q(salary_min__lte=hi) | Q(salary_min__isnull=True, salary_max__isnull=False)
        )

    if data["remote_type"]:
        jobs = jobs.filter(remote_type=data["remote_type"])

    if data["visa_sponsorship"]:
        jobs = jobs.filter(visa_sponsorship=True)

    return jobs


@login_required
def job_search(request):
    """One search workflow with list and map presentations."""
    form = JobSearchForm(request.GET or None)
    jobs = _filter_jobs(form, Job.objects.filter(status=Job.Status.ACTIVE))
    display = "map" if request.GET.get("view") == "map" else "list"
    query = request.GET.copy()
    query.pop("view", None)
    list_url = reverse("jobs:search") + ("?" + query.urlencode() if query else "")
    query["view"] = "map"
    context = {
        "form": form,
        "jobs": jobs,
        "display": display,
        "list_url": list_url,
        "map_url": reverse("jobs:search") + "?" + query.urlencode(),
    }
    if display == "list":
        return render(request, "jobs/job_search.html", context)
    pinned = jobs.filter(lat__isnull=False, lng__isnull=False)
    markers = [
        {
            "id": job.pk,
            "title": job.title,
            "company": job.company,
            "address": job.address,
            "remote_type": job.get_remote_type_display(),
            "visa_sponsorship": job.visa_sponsorship,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "lat": job.lat,
            "lng": job.lng,
            "url": reverse("jobs:detail", args=[job.pk]),
        }
        for job in pinned
    ]
    profile = JobSeekerProfile.objects.filter(user=request.user).first()
    commute_radius = profile.commute_radius if profile else None
    context.update({
        "markers": markers,
        "unpinned_count": jobs.count() - len(markers),
        "radius_form": CommuteRadiusForm(initial={"radius": commute_radius}),
        "commute_radius": commute_radius,
    })
    return render(request, "jobs/job_search.html", context)


@login_required
def job_map(request):
    """Keep existing bookmarks pointing to the unified search's map view."""
    query = request.GET.copy()
    query["view"] = "map"
    return redirect(reverse("jobs:search") + "?" + query.urlencode())


@role_required(User.Role.JOB_SEEKER)
@require_POST
def commute_radius(request):
    form = CommuteRadiusForm(request.POST)
    if form.is_valid():
        profile, _ = JobSeekerProfile.objects.get_or_create(user=request.user)
        profile.commute_radius = form.cleaned_data["radius"]
        profile.save(update_fields=["commute_radius"])
        if profile.commute_radius:
            messages.success(request, f"Your commute radius is now {profile.commute_radius} miles.")
        else:
            messages.success(request, "Your commute radius has been cleared.")
    else:
        messages.error(request, "Pick one of the listed distances.")
    # Send the job seeker back to the map with the same search filters.
    query = request.META.get("QUERY_STRING", "")
    return redirect(reverse("jobs:map") + ("?" + query if query else ""))


@admin_required
def moderation_list(request):
    status = request.GET.get("status", "")
    jobs = Job.objects.select_related("recruiter")
    if status in Job.Status.values:
        jobs = jobs.filter(status=status)
    return render(request, "jobs/moderation.html", {"jobs": jobs, "status": status})


@require_POST
@admin_required
def job_remove(request, pk):
    job = get_object_or_404(Job, pk=pk)
    job.status = Job.Status.REMOVED
    job.save(update_fields=["status"])
    messages.success(request, f'Removed "{job.title}".')
    return redirect("jobs:moderation")


@require_POST
@admin_required
def job_restore(request, pk):
    job = get_object_or_404(Job, pk=pk)
    job.status = Job.Status.ACTIVE
    job.save(update_fields=["status"])
    messages.success(request, f'Restored "{job.title}".')
    return redirect("jobs:moderation")
