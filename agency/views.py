from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.db import transaction
from django.views.decorators.http import require_POST, require_safe
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ClientForm, ContentDeliveryForm, ContractBuilderForm, ContractSignatureForm, ContractTemplateForm, FinancialEntryForm
from .models import Client, ContentDelivery, Contract, ContractTemplate, FinancialEntry, TeamMember, Task
from .access import capabilities
from .pdf import build_contract_pdf, build_financial_report_pdf


def month_bounds(day=None):
    day = day or timezone.localdate()
    start = day.replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


def requested_month(request):
    value = request.GET.get("month", "")
    try:
        return date.fromisoformat(f"{value}-01") if value else timezone.localdate().replace(day=1)
    except ValueError:
        return timezone.localdate().replace(day=1)


def finance_context(request):
    start, end = month_bounds(requested_month(request))
    entries = FinancialEntry.objects.filter(due_date__gte=start, due_date__lt=end).select_related("client", "contract")
    selected_kind = request.GET.get("kind", "")
    selected_status = request.GET.get("status", "")
    selected_client = request.GET.get("client", "")
    if selected_kind in FinancialEntry.Kind.values:
        entries = entries.filter(kind=selected_kind)
    if selected_status in FinancialEntry.Status.values:
        entries = entries.filter(status=selected_status)
    else:
        entries = entries.exclude(status=FinancialEntry.Status.CANCELLED)
    if selected_client.isdigit():
        entries = entries.filter(client_id=int(selected_client))

    projected = FinancialEntry.objects.filter(due_date__gte=start, due_date__lt=end).exclude(status=FinancialEntry.Status.CANCELLED)
    realized = FinancialEntry.objects.filter(status=FinancialEntry.Status.PAID, paid_date__gte=start, paid_date__lt=end)
    if selected_kind in FinancialEntry.Kind.values:
        projected = projected.filter(kind=selected_kind)
        realized = realized.filter(kind=selected_kind)
    if selected_client.isdigit():
        projected = projected.filter(client_id=int(selected_client))
        realized = realized.filter(client_id=int(selected_client))
    if selected_status in FinancialEntry.Status.values:
        projected = projected.filter(status=selected_status)
        if selected_status != FinancialEntry.Status.PAID:
            realized = realized.none()
    projected_income = projected.filter(kind=FinancialEntry.Kind.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    projected_expense = projected.filter(kind=FinancialEntry.Kind.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    realized_income = realized.filter(kind=FinancialEntry.Kind.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    realized_expense = realized.filter(kind=FinancialEntry.Kind.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    pending_income = projected.filter(kind=FinancialEntry.Kind.INCOME, status=FinancialEntry.Status.PENDING).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    pending_expense = projected.filter(kind=FinancialEntry.Kind.EXPENSE, status=FinancialEntry.Status.PENDING).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    overdue = projected.filter(status=FinancialEntry.Status.PENDING, due_date__lt=timezone.localdate())
    category_rows = list(projected.filter(kind=FinancialEntry.Kind.EXPENSE).values("category").annotate(total=Sum("amount")).order_by("-total"))
    for row in category_rows:
        row["percent"] = round(float(row["total"] / projected_expense * 100), 1) if projected_expense else 0
    cash_rows = list(realized.values("paid_date").annotate(income=Sum("amount", filter=Q(kind=FinancialEntry.Kind.INCOME)), expense=Sum("amount", filter=Q(kind=FinancialEntry.Kind.EXPENSE))).order_by("paid_date"))
    balance = Decimal("0")
    for row in cash_rows:
        row["income"] = row["income"] or Decimal("0")
        row["expense"] = row["expense"] or Decimal("0")
        balance += row["income"] - row["expense"]
        row["balance"] = balance
    balances = [Decimal("0")] + [row["balance"] for row in cash_rows]
    floor, ceiling = min(balances), max(balances)
    spread = ceiling - floor or Decimal("1")
    cash_points = " ".join(f"{15 + index * 570 / max(len(balances) - 1, 1):.1f},{165 - float((value - floor) / spread) * 140:.1f}" for index, value in enumerate(balances))
    tab = request.GET.get("tab", "summary")
    if tab not in ("summary", "entries", "cash"):
        tab = "summary"
    tabs = {}
    for key in ("summary", "entries", "cash"):
        params = request.GET.copy()
        params["tab"] = key
        tabs[key] = "?" + params.urlencode()
    return {
        "category_rows": category_rows,
        "cash_rows": cash_rows,
        "cash_points": cash_points,
        "finance_tab": tab,
        "finance_tabs": tabs,
        "entries": entries,
        "month": start,
        "month_value": start.strftime("%Y-%m"),
        "projected_income": projected_income,
        "projected_expense": projected_expense,
        "projected_balance": projected_income - projected_expense,
        "realized_income": realized_income,
        "realized_expense": realized_expense,
        "realized_balance": realized_income - realized_expense,
        "pending_income": pending_income,
        "pending_expense": pending_expense,
        "overdue_count": overdue.count(),
        "overdue_total": overdue.aggregate(total=Sum("amount"))["total"] or Decimal("0"),
        "clients": Client.objects.order_by("trade_name"),
        "kind_choices": FinancialEntry.Kind.choices,
        "status_choices": FinancialEntry.Status.choices,
        "selected_kind": selected_kind,
        "selected_status": selected_status,
        "selected_client": selected_client,
    }


@login_required
def dashboard(request):
    start, end = month_bounds()
    paid = FinancialEntry.objects.filter(status=FinancialEntry.Status.PAID, paid_date__gte=start, paid_date__lt=end)
    income = paid.filter(kind=FinancialEntry.Kind.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expense = paid.filter(kind=FinancialEntry.Kind.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    deliveries = ContentDelivery.objects.filter(scheduled_for__gte=start, scheduled_for__lt=end)
    context = {
        "active_clients": Client.objects.filter(status=Client.Status.ACTIVE).count(),
        "active_contracts": Contract.objects.filter(status__in=(Contract.Status.SENT, Contract.Status.SIGNED), start_date__lt=end, end_date__gte=start).count(),
        "pending_signatures": Contract.objects.filter(status=Contract.Status.SENT).count(),
        "month_deliveries": deliveries.count(),
        "published_deliveries": deliveries.filter(status=ContentDelivery.Status.PUBLISHED).count(),
        "income": income,
        "expense": expense,
        "balance": income - expense,
        "upcoming_deliveries": deliveries.exclude(status=ContentDelivery.Status.CANCELLED).select_related("contract__client")[:8],
        "late_entries": FinancialEntry.objects.filter(status=FinancialEntry.Status.PENDING, due_date__lt=timezone.localdate()).select_related("client")[:6],
        "open_tasks": Task.objects.exclude(status=Task.Status.DONE).count(),
        "late_tasks": Task.objects.exclude(status=Task.Status.DONE).filter(due_date__lt=timezone.localdate()).count(),
        "upcoming_tasks": Task.objects.exclude(status=Task.Status.DONE).select_related("assignee", "client").order_by("due_date")[:6],
        "team_count": TeamMember.objects.filter(is_active=True).count(),
    }
    return render(request, "agency/dashboard.html", context)


@login_required
def client_list(request):
    query = request.GET.get("q", "").strip()
    clients = Client.objects.annotate(contract_count=Count("contracts"))
    if query:
        clients = clients.filter(Q(trade_name__icontains=query) | Q(legal_name__icontains=query) | Q(contact_name__icontains=query))
    return render(request, "agency/client_list.html", {"clients": clients, "query": query})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    start, end = month_bounds()
    contracts = client.contracts.prefetch_related("quotas")
    deliveries = ContentDelivery.objects.filter(contract__client=client, scheduled_for__gte=start, scheduled_for__lt=end).select_related("contract")
    return render(request, "agency/client_detail.html", {"client": client, "contracts": contracts, "deliveries": deliveries})


@login_required
def client_form(request, pk=None):
    instance = get_object_or_404(Client, pk=pk) if pk else None
    form = ClientForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        messages.success(request, "Cliente salvo com sucesso.")
        return redirect(client)
    return render(
        request,
        "agency/entity_form.html",
        {
            "form": form,
            "title": "Editar cliente" if instance else "Novo cliente",
            "eyebrow": "Carteira de clientes",
            "description": "Centralize dados comerciais, contato e situação do relacionamento.",
            "back_url": reverse("agency:client_detail", kwargs={"pk": instance.pk}) if instance else reverse("agency:client_list"),
            "submit_label": "Salvar cliente",
        },
    )


@login_required
def contract_list(request):
    contracts = Contract.objects.select_related("client").prefetch_related("quotas")
    return render(request, "agency/contract_list.html", {"contracts": contracts})


@login_required
def contract_builder(request):
    form = ContractBuilderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contract = form.save()
        messages.success(request, "Contrato gerado com sucesso. Confira o documento antes de enviá-lo para assinatura.")
        return redirect("agency:contract_detail", pk=contract.pk)
    return render(request, "agency/contract_builder.html", {"form": form})


@login_required
def contract_update(request, pk):
    contract = get_object_or_404(Contract.objects.prefetch_related("quotas"), pk=pk)
    if contract.signed_at:
        messages.error(request, "Um contrato assinado não pode ser alterado. Crie um novo contrato ou aditivo.")
        return redirect("agency:contract_detail", pk=contract.pk)
    form = ContractBuilderForm(request.POST or None, instance=contract)
    if request.method == "POST" and form.is_valid():
        contract = form.save()
        messages.success(request, "Contrato atualizado com sucesso.")
        return redirect("agency:contract_detail", pk=contract.pk)
    return render(request, "agency/contract_builder.html", {"form": form, "editing": True, "contract": contract})


@login_required
def contract_detail(request, pk):
    contract = get_object_or_404(Contract.objects.select_related("client", "template").prefetch_related("quotas"), pk=pk)
    return render(request, "agency/contract_detail.html", {"contract": contract})


@login_required
@require_safe
def contract_view(request, pk):
    contract = get_object_or_404(Contract.objects.select_related("client").prefetch_related("quotas"), pk=pk)
    response = render(request, "agency/contract_sign.html", {
        "contract": contract, "internal_preview": True, "signed": bool(contract.signed_at),
    })
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def contract_pdf(request, pk):
    contract = get_object_or_404(Contract.objects.select_related("client").prefetch_related("quotas"), pk=pk)
    return _pdf_response(contract)


@login_required
def template_library(request):
    if not capabilities(request.user)["can_view_contracts"]:
        raise PermissionDenied
    return render(request, "agency/template_library.html", {"templates": ContractTemplate.objects.all()})


@login_required
def template_editor(request, pk=None):
    if not capabilities(request.user)["can_edit_contracts"]:
        raise PermissionDenied
    instance = get_object_or_404(ContractTemplate, pk=pk) if pk else None
    form = ContractTemplateForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        template = form.save()
        messages.success(request, "Modelo de contrato salvo com sucesso.")
        return redirect("agency:template_edit", pk=template.pk)
    return render(request, "agency/template_editor.html", {"form": form, "template": instance})


@login_required
def delivery_list(request):
    start, end = month_bounds(requested_month(request))
    queryset = ContentDelivery.objects.filter(scheduled_for__gte=start, scheduled_for__lt=end).select_related("contract__client", "assignee")
    query = request.GET.get("q", "").strip()
    assignee = request.GET.get("assignee", "")
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(contract__client__trade_name__icontains=query))
    if assignee.isdigit():
        queryset = queryset.filter(assignee_id=int(assignee))
    deliveries = list(
        queryset
    )
    columns = [
        {
            "key": status,
            "label": label,
            "items": [item for item in deliveries if item.status == status],
        }
        for status, label in ContentDelivery.Status.choices
    ]
    return render(request, "agency/delivery_list.html", {"deliveries": deliveries, "columns": columns, "month": start, "month_value": start.strftime("%Y-%m"), "query": query, "selected_assignee": assignee, "members": TeamMember.objects.all(), "status_choices": ContentDelivery.Status.choices})


@login_required
def delivery_form(request, pk=None):
    instance = get_object_or_404(ContentDelivery, pk=pk) if pk else None
    form = ContentDeliveryForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Material salvo e atualizado no fluxo de produção.")
        return redirect("agency:delivery_list")
    return render(
        request,
        "agency/entity_form.html",
        {
            "form": form,
            "title": "Editar material" if instance else "Novo material",
            "eyebrow": "Produção de conteúdo",
            "description": "Planeje o formato, a data e a etapa atual de cada entrega.",
            "back_url": reverse("agency:delivery_list"),
            "submit_label": "Salvar material",
        },
    )


@login_required
def finance(request):
    return render(request, "agency/finance.html", finance_context(request))


@login_required
def financial_report_pdf(request):
    context = finance_context(request)
    response = HttpResponse(build_financial_report_pdf(context), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="relatorio-financeiro-{context["month_value"]}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def financial_entry_form(request, pk=None):
    instance = get_object_or_404(FinancialEntry, pk=pk) if pk else None
    form = FinancialEntryForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lançamento financeiro salvo com sucesso.")
        return redirect("agency:finance")
    return render(
        request,
        "agency/entity_form.html",
        {
            "form": form,
            "title": "Editar lançamento" if instance else "Novo lançamento",
            "eyebrow": "Gestão financeira",
            "description": "Registre entradas, saídas, vencimentos e pagamentos em um só lugar.",
            "back_url": reverse("agency:finance"),
            "submit_label": "Salvar lançamento",
        },
    )


@login_required
@require_POST
@transaction.atomic
def financial_settle(request, pk):
    entry = get_object_or_404(FinancialEntry.objects.select_for_update(), pk=pk)
    if entry.status == FinancialEntry.Status.PENDING:
        entry.status = FinancialEntry.Status.PAID
        entry.paid_date = timezone.localdate()
        entry.save(update_fields=["status", "paid_date", "updated_at"])
        messages.success(request, "Pagamento registrado com a data de hoje.")
    else:
        messages.info(request, "Este lançamento já foi pago ou cancelado; nenhum valor foi duplicado.")
    return redirect(reverse("agency:finance") + "?tab=entries&month=" + entry.due_date.strftime("%Y-%m"))


@login_required
def financial_csv(request):
    import csv
    context = finance_context(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="financeiro-{context["month_value"]}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Vencimento", "Descrição", "Categoria", "Cliente", "Tipo", "Valor", "Situação", "Pagamento", "Forma", "Favorecido"])
    def safe(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value
    for entry in context["entries"]:
        writer.writerow([entry.due_date.isoformat(), safe(entry.description), safe(entry.category), safe(entry.client), entry.get_kind_display(), str(entry.amount).replace(".", ","), entry.get_status_display(), entry.paid_date.isoformat() if entry.paid_date else "", entry.get_payment_method_display(), safe(entry.counterparty)])
    return response


@login_required
@require_POST
@transaction.atomic
def financial_generate(request):
    import calendar
    value = request.POST.get("month", "")
    try:
        start = date.fromisoformat(value + "-01")
    except ValueError:
        messages.error(request, "Selecione uma competência válida.")
        return redirect("agency:finance")
    start, end = month_bounds(start)
    contracts = Contract.objects.select_for_update().filter(status=Contract.Status.SIGNED, start_date__lt=end, end_date__gte=start, monthly_value__gt=0)
    created = 0
    for contract in contracts:
        due = start.replace(day=min(contract.billing_day, calendar.monthrange(start.year, start.month)[1]))
        due = max(due, contract.start_date)
        _, is_new = FinancialEntry.objects.get_or_create(contract=contract, billing_month=start, defaults={"client": contract.client, "kind": FinancialEntry.Kind.INCOME, "description": f"{contract.title} · {start:%m/%Y}"[:180], "category": "Mensalidades de contratos", "amount": contract.monthly_value, "due_date": due, "status": FinancialEntry.Status.PENDING, "notes": "Mensalidade integral gerada pelo contrato. Confira condições de proporcionalidade antes de cobrar."})
        created += is_new
    messages.success(request, f"{created} mensalidade(s) pendente(s) gerada(s). Competências já geradas foram preservadas.")
    return redirect(reverse("agency:finance") + "?tab=entries&month=" + value)


def sign_contract(request, token):
    contract = get_object_or_404(Contract.objects.select_related("client").prefetch_related("quotas"), signature_token=token)
    if contract.signed_at:
        return render(request, "agency/contract_sign.html", {"contract": contract, "signed": True})
    if contract.status != Contract.Status.SENT:
        return render(request, "agency/contract_sign.html", {"contract": contract, "unavailable": True}, status=410)

    form = ContractSignatureForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contract.signer_name = form.cleaned_data["signer_name"]
        contract.signer_tax_id = form.cleaned_data["signer_tax_id"]
        contract.signer_email = form.cleaned_data["signer_email"]
        contract.signed_at = timezone.now()
        contract.signature_ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")
        contract.signature_user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]
        contract.status = Contract.Status.SIGNED
        contract.signature_hash = contract.build_signature_hash()
        contract.save()
        return redirect(contract.get_signing_url())
    return render(request, "agency/contract_sign.html", {"contract": contract, "form": form})


def public_contract_pdf(request, token):
    contract = get_object_or_404(Contract.objects.select_related("client").prefetch_related("quotas"), signature_token=token)
    if contract.status not in (Contract.Status.SENT, Contract.Status.SIGNED):
        return HttpResponse("Contrato indisponível.", status=410, content_type="text/plain; charset=utf-8")
    return _pdf_response(contract)


def _pdf_response(contract):
    response = HttpResponse(build_contract_pdf(contract), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="contrato-{contract.pk}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    return response
