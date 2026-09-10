import hashlib
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Client(models.Model):
    class Kind(models.TextChoices):
        STORE = "store", "Loja / comércio"
        SERVICE = "service", "Prestador de serviços"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        LEAD = "lead", "Em negociação"
        ACTIVE = "active", "Ativo"
        PAUSED = "paused", "Pausado"
        INACTIVE = "inactive", "Inativo"

    trade_name = models.CharField("nome do cliente", max_length=140)
    legal_name = models.CharField("razão social / nome completo", max_length=180, blank=True)
    tax_id = models.CharField("CPF / CNPJ", max_length=24, unique=True, null=True, blank=True)
    kind = models.CharField("tipo", max_length=12, choices=Kind.choices, default=Kind.STORE)
    status = models.CharField("status", max_length=12, choices=Status.choices, default=Status.ACTIVE)
    contact_name = models.CharField("pessoa de contato", max_length=120, blank=True)
    email = models.EmailField("e-mail", blank=True)
    phone = models.CharField("telefone", max_length=24, blank=True)
    address = models.TextField("endereço", blank=True)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ("trade_name",)
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.trade_name

    def get_absolute_url(self):
        return reverse("agency:client_detail", kwargs={"pk": self.pk})


class ContractTemplate(models.Model):
    name = models.CharField("nome do modelo", max_length=160)
    content = models.TextField(
        "conteúdo",
        help_text=(
            "Variáveis disponíveis: [[cliente_nome]], [[cliente_razao_social]], "
            "[[cliente_documento]], [[cliente_endereco]], [[contrato_nome]], "
            "[[data_inicio]], [[data_fim]], [[valor_mensal]], [[dia_vencimento]] "
            "e [[pacote_mensal]]."
        ),
    )
    is_active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "modelo de contrato"
        verbose_name_plural = "modelos de contrato"

    def __str__(self):
        return self.name

    def render(self, context):
        rendered = self.content
        for key, value in context.items():
            rendered = rendered.replace(f"[[{key}]]", str(value or "—"))
        return rendered


class Contract(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        SENT = "sent", "Enviado para assinatura"
        SIGNED = "signed", "Assinado"
        CANCELLED = "cancelled", "Cancelado"

    client = models.ForeignKey(Client, verbose_name="cliente", on_delete=models.PROTECT, related_name="contracts")
    template = models.ForeignKey(
        ContractTemplate,
        verbose_name="modelo utilizado",
        on_delete=models.SET_NULL,
        related_name="contracts",
        null=True,
        blank=True,
    )
    title = models.CharField("nome do contrato / pacote", max_length=160)
    start_date = models.DateField("início")
    end_date = models.DateField("término")
    monthly_value = models.DecimalField("valor mensal", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    billing_day = models.PositiveSmallIntegerField("dia de vencimento", default=10)
    terms = models.TextField("termos do contrato")
    status = models.CharField("status", max_length=12, choices=Status.choices, default=Status.DRAFT)
    signature_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    signer_name = models.CharField("nome do signatário", max_length=160, blank=True)
    signer_tax_id = models.CharField("CPF do signatário", max_length=24, blank=True)
    signer_email = models.EmailField("e-mail do signatário", blank=True)
    signed_at = models.DateTimeField("assinado em", null=True, blank=True)
    signature_ip = models.GenericIPAddressField("IP da assinatura", null=True, blank=True)
    signature_user_agent = models.CharField("navegador da assinatura", max_length=300, blank=True)
    signature_hash = models.CharField("comprovante criptográfico", max_length=64, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_date", "-id")
        verbose_name = "contrato"
        verbose_name_plural = "contratos"

    def __str__(self):
        return f"{self.client} — {self.title}"

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "O término não pode ser anterior ao início."})
        if not 1 <= self.billing_day <= 31:
            raise ValidationError({"billing_day": "Informe um dia entre 1 e 31."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = Contract.objects.filter(pk=self.pk).first()
            if original and original.signed_at:
                immutable = ("client_id", "title", "start_date", "end_date", "monthly_value", "terms")
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError("O conteúdo de um contrato assinado é imutável. Crie um aditivo ou novo contrato.")
        super().save(*args, **kwargs)

    def get_signing_url(self):
        return reverse("agency_signing:sign", kwargs={"token": self.signature_token})

    def build_signature_hash(self):
        payload = "|".join(
            [str(self.pk), str(self.signature_token), str(self.client_id), self.title, self.terms, str(self.start_date), str(self.end_date), str(self.monthly_value), self.signer_name, self.signer_tax_id, self.signer_email, self.signed_at.isoformat()]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DeliverableQuota(models.Model):
    class Kind(models.TextChoices):
        STORY = "story", "Stories"
        FEED = "feed", "Feed"
        VIDEO = "video", "Vídeo"
        REEL = "reel", "Reels"
        ARTICLE = "article", "Matéria no portal"
        BANNER = "banner", "Banner"
        OTHER = "other", "Outro"

    contract = models.ForeignKey(Contract, verbose_name="contrato", on_delete=models.CASCADE, related_name="quotas")
    kind = models.CharField("tipo de material", max_length=12, choices=Kind.choices)
    quantity = models.PositiveSmallIntegerField("quantidade mensal")
    notes = models.CharField("detalhes", max_length=180, blank=True)

    class Meta:
        ordering = ("kind",)
        constraints = [models.UniqueConstraint(fields=("contract", "kind"), name="unique_quota_per_contract_kind")]
        verbose_name = "item do pacote"
        verbose_name_plural = "itens do pacote"

    def __str__(self):
        return f"{self.get_kind_display()}: {self.quantity}/mês"


class ContentDelivery(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planejado"
        PRODUCTION = "production", "Em produção"
        APPROVAL = "approval", "Aguardando aprovação"
        PUBLISHED = "published", "Publicado"
        CANCELLED = "cancelled", "Cancelado"

    contract = models.ForeignKey(Contract, verbose_name="contrato", on_delete=models.PROTECT, related_name="deliveries")
    kind = models.CharField("tipo", max_length=12, choices=DeliverableQuota.Kind.choices)
    title = models.CharField("material", max_length=180)
    scheduled_for = models.DateField("data prevista")
    published_at = models.DateTimeField("publicado em", null=True, blank=True)
    status = models.CharField("status", max_length=12, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheduled_for", "id")
        verbose_name = "material"
        verbose_name_plural = "materiais"

    def __str__(self):
        return f"{self.contract.client} — {self.title}"


class FinancialEntry(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Entrada"
        EXPENSE = "expense", "Saída"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PAID = "paid", "Pago"
        CANCELLED = "cancelled", "Cancelado"

    kind = models.CharField("tipo", max_length=8, choices=Kind.choices)
    description = models.CharField("descrição", max_length=180)
    category = models.CharField("categoria", max_length=80, blank=True)
    amount = models.DecimalField("valor", max_digits=12, decimal_places=2)
    due_date = models.DateField("vencimento")
    paid_date = models.DateField("data do pagamento", null=True, blank=True)
    status = models.CharField("status", max_length=10, choices=Status.choices, default=Status.PENDING)
    client = models.ForeignKey(Client, verbose_name="cliente", on_delete=models.PROTECT, related_name="financial_entries", null=True, blank=True)
    contract = models.ForeignKey(Contract, verbose_name="contrato", on_delete=models.PROTECT, related_name="financial_entries", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-due_date", "-id")
        verbose_name = "lançamento financeiro"
        verbose_name_plural = "lançamentos financeiros"

    def __str__(self):
        return self.description

    def clean(self):
        if self.status == self.Status.PAID and not self.paid_date:
            raise ValidationError({"paid_date": "Informe a data do pagamento."})
        if self.amount <= 0:
            raise ValidationError({"amount": "O valor deve ser maior que zero."})
