"""Presentation helpers shared by the workspace shell and Django form fields."""
from django import template

register = template.Library()


@register.simple_tag
def nav_current(request, destination):
    match = getattr(request, "resolver_match", None)
    if not match:
        return ""
    current = match.view_name
    if current == destination:
        return "page"
    groups = {
        "accounts:job_seeker_area": {
            "accounts:edit_job_seeker_profile", "accounts:add_education", "accounts:edit_education",
            "accounts:add_work_experience", "accounts:edit_work_experience",
            "accounts:add_professional_link", "accounts:edit_professional_link",
            "accounts:add_project", "accounts:edit_project",
        },
        "accounts:saved_searches": {"accounts:saved_search_detail"},
        "accounts:user_management": {"accounts:user_create", "accounts:user_edit", "accounts:user_delete"},
        "reports:list": {"reports:detail"},
        "jobs:cart": {"jobs:cart_compare"},
        "jobs:search": {"jobs:detail", "jobs:map", "jobs:apply", "jobs:recommendations"},
        "jobs:mine": {"jobs:create", "jobs:edit", "jobs:detail", "jobs:job_applications", "jobs:application_detail", "jobs:application_status", "jobs:applicant_map", "jobs:candidate_recommendations", "jobs:candidate_profile"},
    }
    if destination == "communications:inbox" and match.namespace == "communications":
        return "true"
    if destination == "jobs:search" and getattr(request.user, "role", "") != "job_seeker":
        return ""
    return "true" if current in groups.get(destination, set()) else ""


@register.filter
def accessible_field(field):
    attrs = {}
    descriptions = []
    if field.help_text:
        descriptions.append(f"{field.auto_id}_helptext")
    if field.errors:
        attrs["aria-invalid"] = "true"
        descriptions.extend(f"{field.auto_id}_error_{index}" for index, _ in enumerate(field.errors, 1))
    if descriptions:
        existing = field.field.widget.attrs.get("aria-describedby", "")
        attrs["aria-describedby"] = " ".join(filter(None, [existing, *descriptions]))
    return field.as_widget(attrs=attrs)
