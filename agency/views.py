from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ContractSignatureForm
from .models import Client, ContentDelivery, Contract, FinancialEntry


def month_bounds(day=None):
    day = day or timezone.localdate()
    start = day.replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


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
def contract_list(request):
    contracts = Contract.objects.select_related("client").prefetch_related("quotas")
    return render(request, "agency/contract_list.html", {"contracts": contracts})


@login_required
def delivery_list(request):
    start, end = month_bounds()
    deliveries = ContentDelivery.objects.filter(scheduled_for__gte=start, scheduled_for__lt=end).select_related("contract__client")
    return render(request, "agency/delivery_list.html", {"deliveries": deliveries, "month": start})


@login_required
def finance(request):
    start, end = month_bounds()
    entries = FinancialEntry.objects.filter(due_date__gte=start, due_date__lt=end).exclude(status=FinancialEntry.Status.CANCELLED).select_related("client", "contract")
    income = entries.filter(kind=FinancialEntry.Kind.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expense = entries.filter(kind=FinancialEntry.Kind.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return render(request, "agency/finance.html", {"entries": entries, "income": income, "expense": expense, "balance": income - expense, "month": start})


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
