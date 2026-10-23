from django.urls import path
from . import views
from . import cart_views, pipeline_views

app_name = "jobs"

urlpatterns = [
    path("cart/", cart_views.cart, name="cart"),
    path("cart/compare/", cart_views.cart_compare, name="cart_compare"),
    path("cart/add/<int:pk>/", cart_views.cart_add, name="cart_add"),
    path("cart/remove/<int:pk>/", cart_views.cart_remove, name="cart_remove"),
    path("pipeline/", pipeline_views.pipeline, name="pipeline"),
    path("pipeline/<int:pk>/move/", pipeline_views.pipeline_move, name="pipeline_move"),
    path("applications/", views.my_applications, name="my_applications"),
    path("<int:pk>/applications/", views.job_applications, name="job_applications"),
    path("<int:pk>/applications/map/", views.applicant_map, name="applicant_map"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/status/", views.application_status, name="application_status"),
    path("new/", views.job_create, name="create"),
    path("mine/", views.my_jobs, name="mine"),
    path("map/", views.job_map, name="map"),
    path("map/commute-radius/", views.commute_radius, name="commute_radius"),
    path("<int:pk>/", views.job_detail, name="detail"),
    path("<int:pk>/apply/", views.job_apply, name="apply"),
    path("<int:pk>/edit/", views.job_edit, name="edit"),
    path("", views.job_search, name="search"),
    path("moderation/", views.moderation_list, name="moderation"),
    path("<int:pk>/remove/", views.job_remove, name="remove"),
    path("<int:pk>/restore/", views.job_restore, name="restore"),
    path(
        "recommendations/",
        views.job_recommendations,
        name="recommendations",
    ),
    path(
        "<int:pk>/candidates/",
        views.candidate_recommendations,
        name="candidate_recommendations",
    ),
    path(
        "<int:pk>/candidates/<int:profile_pk>/",
        views.candidate_profile,
        name="candidate_profile",
    ),
]
