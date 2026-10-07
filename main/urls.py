from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("app.urls")),
    path("manage/", include("managements.urls")),
    path("", include("user.urls")),
    path("admin/", admin.site.urls),
]