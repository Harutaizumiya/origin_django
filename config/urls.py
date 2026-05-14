from django.urls import include, path

from common.views import HomePageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("inventory.urls")),
]
