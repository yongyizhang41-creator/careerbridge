from django.urls import path
from . import views

app_name = "reports"
urlpatterns = [
    path("", views.report_list, name="list"),
    path("submitted/", views.submitted, name="submitted"),
    path("jobs/<int:pk>/new/", views.report_job, name="job"),
    path("users/<int:pk>/new/", views.report_user, name="user"),
    path("<int:pk>/", views.report_detail, name="detail"),
]
