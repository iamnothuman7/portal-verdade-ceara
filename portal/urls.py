from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from .views import health
from agency.work_views import brand_logo

admin.site.site_header = "Portal Verdade Ceará"
admin.site.site_title = "Redação"
admin.site.index_title = "Gestão editorial"

urlpatterns = [
    path("marca/logo/", brand_logo, name="brand_logo"),
    path("marca/simbolo/", brand_logo, {"variant": "compact"}, name="brand_compact_logo"),
    path("marca/painel/", brand_logo, {"variant": "panel"}, name="brand_panel_logo"),
    path("", auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("health/", health, name="health"),
    path("painel/", admin.site.urls),
    path("gestao/", include("agency.urls")),
    path("contrato/", include("agency.signing_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
