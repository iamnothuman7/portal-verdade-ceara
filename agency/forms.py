from decimal import Decimal

from django import forms
from django.db import transaction

from .models import Client, ContentDelivery, Contract, ContractTemplate, DeliverableQuota, FinancialEntry


QUOTA_FIELDS = (
    (DeliverableQuota.Kind.STORY, "Stories"),
    (DeliverableQuota.Kind.FEED, "Feed"),
    (DeliverableQuota.Kind.VIDEO, "Vídeos"),
    (DeliverableQuota.Kind.REEL, "Reels"),
    (DeliverableQuota.Kind.ARTICLE, "Matérias no portal"),
    (DeliverableQuota.Kind.BANNER, "Banners"),
    (DeliverableQuota.Kind.OTHER, "Outros materiais"),
)


def format_currency_br(value):
    formatted = f"{Decimal(value or 0):,.2f}"
    return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


class ContractBuilderForm(forms.ModelForm):
    template = forms.ModelChoiceField(label="Modelo de contrato", queryset=ContractTemplate.objects.none())
    story_quantity = forms.IntegerField(label="Stories", min_value=0, required=False, initial=0)
    feed_quantity = forms.IntegerField(label="Feed", min_value=0, required=False, initial=0)
    video_quantity = forms.IntegerField(label="Vídeos", min_value=0, required=False, initial=0)
    reel_quantity = forms.IntegerField(label="Reels", min_value=0, required=False, initial=0)
    article_quantity = forms.IntegerField(label="Matérias no portal", min_value=0, required=False, initial=0)
    banner_quantity = forms.IntegerField(label="Banners", min_value=0, required=False, initial=0)
    other_quantity = forms.IntegerField(label="Outros materiais", min_value=0, required=False, initial=0)

    class Meta:
        model = Contract
        fields = ("client", "template", "title", "start_date", "end_date", "monthly_value", "billing_day", "status")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "monthly_value": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "billing_day": forms.NumberInput(attrs={"min": "1", "max": "31"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.order_by("trade_name")
        self.fields["template"].queryset = ContractTemplate.objects.filter(is_active=True)
        self.fields["status"].choices = (
            (Contract.Status.DRAFT, Contract.Status.DRAFT.label),
            (Contract.Status.SENT, Contract.Status.SENT.label),
            (Contract.Status.CANCELLED, Contract.Status.CANCELLED.label),
        )
        if self.instance.pk:
            quota_map = {quota.kind: quota.quantity for quota in self.instance.quotas.all()}
            for kind, _ in QUOTA_FIELDS:
                self.fields[f"{kind}_quantity"].initial = quota_map.get(kind, 0)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "studio-input")

    def quota_values(self):
        return [
            (kind, int(self.cleaned_data.get(f"{kind}_quantity") or 0), label)
            for kind, label in QUOTA_FIELDS
        ]

    @transaction.atomic
    def save(self, commit=True):
        contract = super().save(commit=False)
        quotas = self.quota_values()
        package = ", ".join(f"{quantity} {label}" for _, quantity, label in quotas if quantity) or "Pacote personalizado conforme demanda"
        context = {
            "cliente_nome": contract.client.trade_name,
            "cliente_razao_social": contract.client.legal_name or contract.client.trade_name,
            "cliente_documento": contract.client.tax_id or "Não informado",
            "cliente_endereco": contract.client.address or "Não informado",
            "contrato_nome": contract.title,
            "data_inicio": contract.start_date.strftime("%d/%m/%Y"),
            "data_fim": contract.end_date.strftime("%d/%m/%Y"),
            "valor_mensal": format_currency_br(contract.monthly_value),
            "dia_vencimento": contract.billing_day,
            "pacote_mensal": package,
        }
        contract.terms = contract.template.render(context)
        if commit:
            contract.save()
            contract.quotas.all().delete()
            DeliverableQuota.objects.bulk_create(
                DeliverableQuota(contract=contract, kind=kind, quantity=quantity)
                for kind, quantity, _ in quotas
                if quantity
            )
        return contract


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "studio-input")


class ClientForm(StyledModelForm):
    class Meta:
        model = Client
        fields = ("trade_name", "legal_name", "tax_id", "kind", "status", "contact_name", "email", "phone", "address", "notes")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_tax_id(self):
        return self.cleaned_data.get("tax_id") or None


class ContentDeliveryForm(StyledModelForm):
    class Meta:
        model = ContentDelivery
        fields = ("contract", "kind", "title", "scheduled_for", "status", "notes")
        widgets = {
            "scheduled_for": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract"].queryset = Contract.objects.select_related("client").exclude(status=Contract.Status.CANCELLED)


class FinancialEntryForm(StyledModelForm):
    class Meta:
        model = FinancialEntry
        fields = ("kind", "description", "category", "amount", "due_date", "paid_date", "status", "client", "contract", "notes")
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "paid_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.order_by("trade_name")
        self.fields["contract"].queryset = Contract.objects.select_related("client").order_by("client__trade_name", "title")


class ContractTemplateForm(forms.ModelForm):
    class Meta:
        model = ContractTemplate
        fields = ("name", "content", "is_active")
        widgets = {"content": forms.Textarea(attrs={"rows": 24, "class": "studio-editor"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "studio-input")


class ContractSignatureForm(forms.Form):
    signer_name = forms.CharField(label="Nome completo", max_length=160)
    signer_tax_id = forms.CharField(label="CPF", max_length=24)
    signer_email = forms.EmailField(label="E-mail")
    consent = forms.BooleanField(
        label="Li o contrato e concordo com todos os termos. Confirmo que os dados acima são verdadeiros e que este aceite representa minha assinatura eletrônica."
    )
