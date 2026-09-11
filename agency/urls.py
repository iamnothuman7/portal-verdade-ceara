from django.urls import path

from . import views
from . import work_views
from . import production

app_name = "agency"

urlpatterns = [
    path("ajuda/", work_views.help_page, name="help"),
    path("configuracoes/", work_views.settings_form, name="settings_edit"),
    path("equipe/", work_views.team_list, name="team_list"),
    path("equipe/novo/", work_views.team_form, name="team_create"),
    path("equipe/<int:pk>/editar/", work_views.team_form, name="team_edit"),
    path("producao/", production.workspace, name="production_workspace"),
    path("tarefas/", production.workspace, {'source_filter': 'task'}, name="task_list"),
    path("tarefas/nova/", work_views.task_form, name="task_create"),
    path("tarefas/<int:pk>/", work_views.task_detail, name="task_detail"),
    path("tarefas/<int:pk>/editar/", work_views.task_form, name="task_edit"),
    path("tarefas/<int:pk>/etapa/", work_views.task_status, name="task_status"),
    path("materiais/<int:pk>/etapa/", work_views.delivery_status, name="delivery_status"),
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
    path("contratos/<int:pk>/visualizar/", views.contract_view, name="contract_view"),
    path("contratos/<int:pk>/editar/", views.contract_update, name="contract_edit"),
    path("contratos/<int:pk>/pdf/", views.contract_pdf, name="contract_pdf"),
    path("materiais/", production.workspace, {'source_filter': 'delivery'}, name="delivery_list"),
    path("materiais/novo/", views.delivery_form, name="delivery_create"),
    path("materiais/<int:pk>/editar/", views.delivery_form, name="delivery_edit"),
    path("financeiro/", views.finance, name="finance"),
    path("financeiro/relatorio.pdf", views.financial_report_pdf, name="financial_report_pdf"),
    path("financeiro/exportar.csv", views.financial_csv, name="financial_csv"),
    path("financeiro/gerar-mensalidades/", views.financial_generate, name="financial_generate"),
    path("financeiro/<int:pk>/pagar/", views.financial_settle, name="financial_settle"),
    path("financeiro/novo/", views.financial_entry_form, name="financial_entry_create"),
    path("financeiro/<int:pk>/editar/", views.financial_entry_form, name="financial_entry_edit"),
]
