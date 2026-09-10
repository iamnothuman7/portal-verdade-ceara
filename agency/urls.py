from django.urls import path

from . import views

app_name = "agency"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("clientes/", views.client_list, name="client_list"),
    path("clientes/novo/", views.client_form, name="client_create"),
    path("clientes/<int:pk>/editar/", views.client_form, name="client_edit"),
    path("clientes/<int:pk>/", views.client_detail, name="client_detail"),
    path("contratos/", views.contract_list, name="contract_list"),
    path("contratos/gerador/", views.contract_builder, name="contract_builder"),
    path("contratos/modelos/", views.template_library, name="template_library"),
    path("contratos/modelos/novo/", views.template_editor, name="template_create"),
    path("contratos/modelos/<int:pk>/editar/", views.template_editor, name="template_edit"),
    path("contratos/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contratos/<int:pk>/editar/", views.contract_update, name="contract_edit"),
    path("contratos/<int:pk>/pdf/", views.contract_pdf, name="contract_pdf"),
    path("materiais/", views.delivery_list, name="delivery_list"),
    path("materiais/novo/", views.delivery_form, name="delivery_create"),
    path("materiais/<int:pk>/editar/", views.delivery_form, name="delivery_edit"),
    path("financeiro/", views.finance, name="finance"),
    path("financeiro/relatorio.pdf", views.financial_report_pdf, name="financial_report_pdf"),
    path("financeiro/novo/", views.financial_entry_form, name="financial_entry_create"),
    path("financeiro/<int:pk>/editar/", views.financial_entry_form, name="financial_entry_edit"),
]
