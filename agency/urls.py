from django.urls import path

from . import views

app_name = "agency"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("clientes/", views.client_list, name="client_list"),
    path("clientes/<int:pk>/", views.client_detail, name="client_detail"),
    path("contratos/", views.contract_list, name="contract_list"),
    path("materiais/", views.delivery_list, name="delivery_list"),
    path("financeiro/", views.finance, name="finance"),
]
