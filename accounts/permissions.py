from .models import User


def can_view_profile(viewer, profile):
    """Allow the owner, or a recruiter with visibility or application access."""
    if not viewer.is_authenticated or profile is None:
        return False

    if viewer.pk == profile.user_id:
        return True

    if viewer.role != User.Role.RECRUITER:
        return False

    if profile.recruiter_visible:
        return True

    return profile.user.applications.filter(
        job__recruiter=viewer,
    ).exists()