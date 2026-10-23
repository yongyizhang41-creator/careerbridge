from django import forms
from django.contrib import messages
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from .models import Application, CartItem, Job

seeker_required = role_required(User.Role.JOB_SEEKER)


def _cart_items(user):
    return (
        CartItem.objects.filter(owner=user)
        .select_related("job")
        .annotate(applied=Exists(Application.objects.filter(
            applicant=user, job_id=OuterRef("job_id"),
        )))
    )


class ComparisonForm(forms.Form):
    items = forms.ModelMultipleChoiceField(queryset=CartItem.objects.none())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["items"].queryset = _cart_items(user)

    def clean_items(self):
        items = self.cleaned_data["items"]
        if len(items) < 2:
            raise forms.ValidationError("Select at least two jobs to compare.")
        if any(item.job.status != Job.Status.ACTIVE for item in items):
            raise forms.ValidationError("Unavailable jobs cannot be compared. Select available jobs.")
        return items


@seeker_required
def cart(request):
    return render(request, "jobs/cart.html", {"items": _cart_items(request.user)})


@seeker_required
@require_POST
def cart_add(request, pk):
    job = get_object_or_404(Job, pk=pk, status=Job.Status.ACTIVE)
    _, created = CartItem.objects.get_or_create(owner=request.user, job=job)
    messages.success(request, "Job added to your cart." if created else "This job is already in your cart.")
    return redirect("jobs:cart")


@seeker_required
@require_POST
def cart_remove(request, pk):
    item = get_object_or_404(CartItem, pk=pk, owner=request.user)
    item.delete()
    messages.success(request, "Job removed from your cart.")
    return redirect("jobs:cart")


@seeker_required
def cart_compare(request):
    form = ComparisonForm(request.GET, user=request.user)
    if not form.is_valid():
        return render(request, "jobs/cart.html", {
            "items": _cart_items(request.user), "comparison_form": form,
            "selected_ids": request.GET.getlist("items"),
        })
    return render(request, "jobs/cart_compare.html", {"items": form.cleaned_data["items"]})
