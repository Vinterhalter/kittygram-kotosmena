from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from djoser.views import UserViewSet, TokenCreateView
from config.auth import LogoutView
from cats.views import CatViewSet, AchievementViewSet
from care.views import HandoverViewSet, TaskViewSet, CompletionViewSet, IncidentViewSet

router = DefaultRouter()
for prefix, view in [
    ("cats", CatViewSet),
    ("achievements", AchievementViewSet),
    ("handovers", HandoverViewSet),
    ("tasks", TaskViewSet),
    ("completions", CompletionViewSet),
    ("incidents", IncidentViewSet),
]:
    router.register(prefix, view, basename=prefix)
urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/users/", UserViewSet.as_view({"post": "create"})),
    path("api/users/me/", UserViewSet.as_view({"get": "me"})),
    path("api/token/login/", TokenCreateView.as_view()),
    path("api/token/logout/", LogoutView.as_view()),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
