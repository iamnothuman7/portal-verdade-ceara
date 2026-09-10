from django.urls import path

from . import views

app_name = "agency_signing"

urlpatterns = [path("<uuid:token>/", views.sign_contract, name="sign")]
