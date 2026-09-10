from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Client, ContentDelivery, Contract, DeliverableQuota, FinancialEntry


class AgencyTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("gestor", password="uma-senha-forte")
        self.client_record = Client.objects.create(trade_name="Cliente Teste", kind=Client.Kind.STORE)
        self.contract = Contract.objects.create(
            client=self.client_record,
            title="Pacote Essencial",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_value=Decimal("1500.00"),
            terms="Serviços de comunicação definidos no pacote.",
            status=Contract.Status.SENT,
        )
        DeliverableQuota.objects.create(contract=self.contract, kind=DeliverableQuota.Kind.STORY, quantity=12)

    def test_login_is_the_only_root_screen(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acesso restrito")

    def test_health_checks_database(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_management_dashboard_requires_login(self):
        response = self.client.get(reverse("agency:dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('agency:dashboard')}")

    def test_authenticated_user_sees_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("agency:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clientes ativos")

    def test_all_internal_sections_require_auth_and_render(self):
        urls = (
            reverse("agency:client_list"),
            reverse("agency:contract_list"),
            reverse("agency:delivery_list"),
            reverse("agency:finance"),
        )
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_contract_signature_records_evidence_and_locks_content(self):
        url = self.contract.get_signing_url()
        response = self.client.post(
            url,
            {"signer_name": "Maria da Silva", "signer_tax_id": "123.456.789-00", "signer_email": "maria@example.com", "consent": "on"},
            HTTP_USER_AGENT="Test Browser",
            HTTP_X_REAL_IP="203.0.113.10",
        )
        self.assertRedirects(response, url)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, Contract.Status.SIGNED)
        self.assertIsNotNone(self.contract.signed_at)
        self.assertEqual(len(self.contract.signature_hash), 64)
        self.assertEqual(self.contract.signature_ip, "203.0.113.10")
        self.contract.terms = "Tentativa de alteração"
        with self.assertRaises(ValidationError):
            self.contract.save()

    def test_draft_contract_cannot_be_signed(self):
        self.contract.status = Contract.Status.DRAFT
        self.contract.save()
        response = self.client.get(self.contract.get_signing_url())
        self.assertEqual(response.status_code, 410)

    def test_financial_totals_are_shown(self):
        today = timezone.localdate()
        FinancialEntry.objects.create(kind=FinancialEntry.Kind.INCOME, description="Mensalidade", amount=Decimal("1000"), due_date=today, paid_date=today, status=FinancialEntry.Status.PAID, client=self.client_record)
        FinancialEntry.objects.create(kind=FinancialEntry.Kind.EXPENSE, description="Ferramenta", amount=Decimal("250"), due_date=today, paid_date=today, status=FinancialEntry.Status.PAID)
        self.client.force_login(self.user)
        response = self.client.get(reverse("agency:dashboard"))
        self.assertContains(response, "750,00")

    def test_monthly_delivery_appears_for_client(self):
        delivery = ContentDelivery.objects.create(contract=self.contract, kind=DeliverableQuota.Kind.STORY, title="Campanha da semana", scheduled_for=timezone.localdate())
        self.client.force_login(self.user)
        response = self.client.get(reverse("agency:client_detail", kwargs={"pk": self.client_record.pk}))
        self.assertContains(response, delivery.title)
