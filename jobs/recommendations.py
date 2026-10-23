from accounts.models import JobSeekerProfile, User
from django.core.exceptions import PermissionDenied
from .models import Job


def normalized_skills(skill_list):
    return {
        skill.strip().casefold()
        for skill in skill_list
        if skill.strip()
    }


def recommend_jobs(user):
    if not user.is_authenticated or user.role != User.Role.JOB_SEEKER:
        return []

    profile = JobSeekerProfile.objects.filter(user=user).first()
    if profile is None:
        return []

    candidate_skills = normalized_skills(profile.skill_list())
    if not candidate_skills:
        return []

    applied_job_ids = user.applications.values_list("job_id", flat=True)
    jobs = (
        Job.objects.filter(status=Job.Status.ACTIVE)
        .exclude(pk__in=applied_job_ids)
        .order_by("-created_at", "-pk")
    )

    recommendations = []
    for job in jobs:
        matched_skills = sorted(
            candidate_skills & normalized_skills(job.skill_list())
        )
        if matched_skills:
            recommendations.append({
                "job": job,
                "matched_skills": matched_skills,
                "score": len(matched_skills),
            })

    recommendations.sort(
        key=lambda recommendation: recommendation["score"],
        reverse=True,
    )
    return recommendations



def recommend_candidates(recruiter, job):
    if (
        not recruiter.is_authenticated
        or recruiter.role != User.Role.RECRUITER
        or job.recruiter_id != recruiter.pk
    ):
        raise PermissionDenied

    if job.status != Job.Status.ACTIVE:
        return []

    job_skills = normalized_skills(job.skill_list())
    if not job_skills:
        return []

    applicant_ids = job.applications.values_list("applicant_id", flat=True)
    profiles = (
        JobSeekerProfile.objects.filter(
            recruiter_visible=True,
            user__role=User.Role.JOB_SEEKER,
            user__is_active=True,
        )
        .exclude(user_id__in=applicant_ids)
        .select_related("user")
        .order_by("pk")
    )

    recommendations = []
    for profile in profiles:
        matched_skills = sorted(
            job_skills & normalized_skills(profile.skill_list())
        )
        if matched_skills:
            recommendations.append({
                "profile": profile,
                "matched_skills": matched_skills,
                "score": len(matched_skills),
            })

    recommendations.sort(
        key=lambda recommendation: recommendation["score"],
        reverse=True,
    )
    return recommendations