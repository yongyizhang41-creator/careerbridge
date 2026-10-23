from django import forms
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from .forms import ApplicationStatusForm
from .models import Application, Job

recruiter_required = role_required(User.Role.RECRUITER)


class PipelineMoveForm(ApplicationStatusForm):
    expected_status = forms.ChoiceField(choices=Application.Status.choices)


@recruiter_required
def pipeline(request):
    jobs = Job.objects.filter(recruiter=request.user)
    selected_job = None
    applications = Application.objects.filter(job__recruiter=request.user)
    if request.GET.get("job"):
        if not request.GET["job"].isdecimal():
            raise Http404
        selected_job = get_object_or_404(jobs, pk=request.GET["job"])
        applications = applications.filter(job=selected_job)
    columns = [{"value": value, "label": label, "applications": []} for value, label in Application.Status.choices]
    by_status = {column["value"]: column for column in columns}
    for application in applications.select_related("job", "applicant").order_by("-created_at", "-pk"):
        by_status[application.status]["applications"].append(application)
    return render(request, "jobs/pipeline.html", {
        "columns": columns, "jobs": jobs, "selected_job": selected_job,
        "statuses": Application.Status.choices,
    })


@recruiter_required
@require_POST
def pipeline_move(request, pk):
    wants_json = request.headers.get("Accept") == "application/json"
    application = get_object_or_404(
        Application, pk=pk, job__recruiter=request.user,
    )
    form = PipelineMoveForm(request.POST, instance=application)
    if not form.is_valid():
        if wants_json:
            return JsonResponse({"error": "Choose a valid stage and reload the board if necessary."}, status=400)
        messages.error(request, "Choose a valid stage and try again.")
    else:
        # A conditional update prevents stale moves on SQLite as well as other databases.
        updated = Application.objects.filter(
            pk=application.pk, job__recruiter=request.user,
            status=form.cleaned_data["expected_status"],
        ).update(status=form.cleaned_data["status"])
        if not updated:
            if wants_json:
                return JsonResponse({"error": "This application changed in another tab. Reload the board before moving it."}, status=409)
            messages.error(request, "This application changed in another tab. Please try again from the refreshed board.")
        else:
            if wants_json:
                return JsonResponse({"status": application.status, "label": application.get_status_display()})
            messages.success(request, "Application moved to " + application.get_status_display() + ".")
    url = reverse("jobs:pipeline")
    if request.POST.get("job") == str(application.job_id):
        url += "?job=" + str(application.job_id)
    return redirect(url)
