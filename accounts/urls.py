from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, user_management


app_name = "accounts"

urlpatterns = [
    path("users/", user_management.user_management, name="user_management"),
    path("users/add/", user_management.user_create, name="user_create"),
    path("users/<int:pk>/edit/", user_management.user_edit, name="user_edit"),
    path("users/delete/", user_management.user_delete, name="user_delete"),
    path("register/", views.register, name="register"),
    path(
        "registration-complete/",
        views.registration_complete,
        name="registration_complete",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
    path(
        "job-seeker/",
        views.job_seeker_area,
        name="job_seeker_area",
    ),
    path(
        "recruiter/",
        views.recruiter_area,
        name="recruiter_area",
    ),
    path("reports/", views.reporting, name="reporting"),
    path(
        "reports/users.csv",
        views.export_users_csv,
        name="export_users_csv",
    ),
    path(
        "job-seeker/profile/",
        views.edit_job_seeker_profile,
        name="edit_job_seeker_profile",
    ),
    path(
        "reports/jobs.csv",
        views.export_jobs_csv,
        name="export_jobs_csv",
    ),
    path(
        "reports/applications.csv",
        views.export_applications_csv,
        name="export_applications_csv",
    ),
    path(
        "job-seeker/profile/education/add/",
        views.add_education,
        name="add_education",
    ),
    path(
        "job-seeker/profile/education/<int:pk>/edit/",
        views.edit_education,
        name="edit_education",
    ),
    path(
        "job-seeker/profile/education/<int:pk>/delete/",
        views.delete_education,
        name="delete_education",
    ),
    path(
        "job-seeker/profile/work-experience/add/",
        views.add_work_experience,
        name="add_work_experience",
    ),
    path(
        "job-seeker/profile/work-experience/<int:pk>/edit/",
        views.edit_work_experience,
        name="edit_work_experience",
    ),
    path(
        "job-seeker/profile/work-experience/<int:pk>/delete/",
        views.delete_work_experience,
        name="delete_work_experience",
    ),
    path(
        "job-seeker/profile/links/add/",
        views.add_professional_link,
        name="add_professional_link",
    ),
    path(
        "job-seeker/profile/links/<int:pk>/edit/",
        views.edit_professional_link,
        name="edit_professional_link",
    ),
    path(
        "job-seeker/profile/links/<int:pk>/delete/",
        views.delete_professional_link,
        name="delete_professional_link",
    ),
    path(
        "job-seeker/profile/projects/add/",
        views.add_project,
        name="add_project",
    ),
    path(
        "job-seeker/profile/projects/<int:pk>/edit/",
        views.edit_project,
        name="edit_project",
    ),
    path(
        "job-seeker/profile/projects/<int:pk>/delete/",
        views.delete_project,
        name="delete_project",
    ),
    path(
        "candidates/", 
        views.candidate_search, 
        name="candidate_search"
    ),
    path(
        "candidates/save/",
         views.save_candidate_search, 
         name="save_candidate_search"
    ),
    path(
        "candidates/saved/", 
         views.saved_searches, 
         name="saved_searches"
    ),
    path(
        "candidates/saved/<int:pk>/", 
        views.saved_search_detail,
        name="saved_search_detail"
    ),
    path(
        "candidates/saved/<int:pk>/delete/",
        views.delete_saved_search,
        name="delete_saved_search",
    ),
]
