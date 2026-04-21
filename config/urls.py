from django.urls import include, path

from common.views import HomePageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("api/", include("inventory.urls")),
]
