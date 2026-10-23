"""CareerBridge user administration; Django Admin remains a separate interface."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import role_required
from .forms import (
    ManagedUserCreationForm, ManagedUserForm, ManagedUserFormSet, ManagedUserRowForm,
)
from .models import User


def require_user_permission(request, action):
    if not request.user.is_staff or not request.user.has_perm(f"accounts.{action}_user"):
        raise PermissionDenied


def visible_users(request):
    ordering = request.GET.get("sort", "username")
    if ordering.removeprefix("-") not in {"username", "email", "role", "is_staff", "is_active"}:
        ordering = "username"
    users = User.objects.order_by(ordering, "pk")
    query = request.GET.get("q", "").strip()
    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
    role = request.GET.get("role", "")
    if role in User.Role.values:
        users = users.filter(role=role)
    for field in ("is_staff", "is_active"):
        value = request.GET.get(field, "")
        if value in ("yes", "no"):
            users = users.filter(**{field: value == "yes"})
    return users


@role_required(User.Role.ADMINISTRATOR)
@require_http_methods(["GET", "POST"])
def user_management(request):
    if not request.user.is_staff or not (
        request.user.has_perm("accounts.view_user") or request.user.has_perm("accounts.change_user")
    ):
        raise PermissionDenied
    with transaction.atomic():
        users = visible_users(request)
        page = Paginator(users, 50).get_page(request.GET.get("page"))
        ids = [user.pk for user in page.object_list]
        rows = User.objects.filter(pk__in=ids).order_by(*users.query.order_by)
        if request.method == "POST":
            require_user_permission(request, "change")
            rows = rows.select_for_update()
        RowSet = modelformset_factory(
            User, form=ManagedUserRowForm, formset=ManagedUserFormSet,
            extra=0, max_num=50, absolute_max=50,
        )
        formset = RowSet(
            request.POST if request.method == "POST" else None,
            queryset=rows, form_kwargs={"actor": request.user},
        )
        if request.method == "POST" and formset.is_valid():
            formset.save()
            messages.success(request, "User changes saved.")
            return redirect(request.get_full_path())
        if not request.user.has_perm("accounts.change_user"):
            for form in formset:
                for field in form.fields.values():
                    field.disabled = True
        params = request.GET.copy()
        params.pop("page", None)
        sort_headers = []
        for field, label in [("username", "Username"), ("email", "Email address"),
                             ("role", "Role"), ("is_staff", "Staff status"), ("is_active", "Active")]:
            sort_params = params.copy()
            sort_params["sort"] = f"-{field}" if request.GET.get("sort", "username") == field else field
            sort_headers.append((label, sort_params.urlencode()))
        return render(request, "accounts/user_management.html", {
            "formset": formset, "page_obj": page, "roles": User.Role.choices,
            "filters": request.GET, "page_query": params.urlencode(),
            "sort_headers": sort_headers,
        })


@role_required(User.Role.ADMINISTRATOR)
@require_http_methods(["GET", "POST"])
def user_create(request):
    require_user_permission(request, "add")
    form = ManagedUserCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "User created. Website administrators need staff access and model permissions assigned separately in Django Admin.")
        return redirect("accounts:user_management")
    return render(request, "accounts/managed_user_form.html", {"form": form, "creating": True})


@role_required(User.Role.ADMINISTRATOR)
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    require_user_permission(request, "change")
    with transaction.atomic():
        user = get_object_or_404(User.objects.select_for_update(), pk=pk)
        form = ManagedUserForm(
            request.POST if request.method == "POST" else None, instance=user, actor=request.user,
        )
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "User saved.")
            return redirect("accounts:user_management")
        return render(request, "accounts/managed_user_form.html", {"form": form, "managed_user": user})


@role_required(User.Role.ADMINISTRATOR)
@require_http_methods(["POST"])
def user_delete(request):
    require_user_permission(request, "delete")
    ids = request.POST.getlist("selected")
    if not ids or len(ids) > 50 or any(not pk.isdecimal() for pk in ids):
        messages.error(request, "Select between 1 and 50 users to delete.")
        return redirect("accounts:user_management")
    with transaction.atomic():
        users = list(User.objects.select_for_update().filter(pk__in=ids).order_by("username"))
        if len(users) != len(set(ids)):
            messages.error(request, "The user list changed. Select users again.")
            return redirect("accounts:user_management")
        if any(user.pk == request.user.pk or (user.is_superuser and not request.user.is_superuser) for user in users):
            messages.error(request, "You cannot delete your own account or a protected superuser.")
            return redirect("accounts:user_management")
        if request.POST.get("confirm") == "yes":
            try:
                User.objects.filter(pk__in=[user.pk for user in users]).delete()
            except ProtectedError:
                messages.error(request, "These users have protected related records and cannot be deleted. Deactivate them instead.")
            else:
                messages.success(request, f"Deleted {len(users)} user account(s).")
            return redirect("accounts:user_management")
        return render(request, "accounts/managed_user_delete.html", {"selected_users": users})
