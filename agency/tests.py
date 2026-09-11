from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Client, ContentDelivery, Contract, ContractTemplate, DeliverableQuota, FinancialEntry


class AgencyTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("gestor", password="uma-senha-forte", is_staff=True)
        self.client_record = Client.objects.create(trade_name="Cliente Teste", kind=Client.Kind.STORE)
        self.template = ContractTemplate.objects.create(
            name="Modelo de teste",
            content=(
                "Contrato [[contrato_nome]] para [[cliente_razao_social]]. "
                "Vigência: [[data_inicio]] a [[data_fim]]. Valor: [[valor_mensal]]. "
                "Vencimento: [[dia_vencimento]]. Pacote: [[pacote_mensal]]."
            ),
        )
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
        self.assertContains(response, "favicon-portal.png")

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

    def test_contract_template_renders_placeholders(self):
        rendered = self.template.render({"contrato_nome": "Plano Redação", "cliente_razao_social": "Empresa Exemplo"})
        self.assertIn("Plano Redação", rendered)
        self.assertIn("Empresa Exemplo", rendered)

    def test_contract_builder_creates_snapshot_and_quotas(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("agency:contract_builder"),
            {
                "client": self.client_record.pk,
                "template": self.template.pk,
                "title": "Pacote Completo",
                "start_date": "2026-09-10",
                "end_date": "2027-09-09",
                "monthly_value": "2300.50",
                "billing_day": "15",
                "status": Contract.Status.SENT,
                "story_quantity": "12",
                "feed_quantity": "4",
                "video_quantity": "2",
                "reel_quantity": "0",
                "article_quantity": "1",
                "banner_quantity": "0",
                "other_quantity": "0",
            },
        )
        created = Contract.objects.get(title="Pacote Completo")
        self.assertRedirects(response, reverse("agency:contract_detail", kwargs={"pk": created.pk}))
        self.assertEqual(created.template, self.template)
        self.assertNotIn("[[", created.terms)
        self.assertIn("R$ 2.300,50", created.terms)
        self.assertEqual(created.quotas.count(), 4)
        self.assertEqual(created.quotas.get(kind=DeliverableQuota.Kind.STORY).quantity, 12)

    def test_contract_editor_replaces_package_before_signature(self):
        self.contract.template = self.template
        self.contract.save(update_fields=("template",))
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("agency:contract_edit", kwargs={"pk": self.contract.pk}),
            {
                "client": self.client_record.pk,
                "template": self.template.pk,
                "title": "Pacote Essencial Atualizado",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "monthly_value": "1800.00",
                "billing_day": "12",
                "status": Contract.Status.SENT,
                "story_quantity": "30",
                "feed_quantity": "5",
                "video_quantity": "0",
                "reel_quantity": "0",
                "article_quantity": "0",
                "banner_quantity": "0",
                "other_quantity": "0",
            },
        )
        self.assertRedirects(response, reverse("agency:contract_detail", kwargs={"pk": self.contract.pk}))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.title, "Pacote Essencial Atualizado")
        self.assertEqual(self.contract.quotas.count(), 2)
        self.assertEqual(self.contract.quotas.get(kind=DeliverableQuota.Kind.STORY).quantity, 30)

    def test_internal_contract_pdf_requires_login_and_is_valid(self):
        url = reverse("agency:contract_pdf", kwargs={"pk": self.contract.pk})
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1000)

    def test_public_pdf_only_allows_sent_or_signed_contracts(self):
        url = reverse("agency_signing:pdf", kwargs={"token": self.contract.signature_token})
        self.assertEqual(self.client.get(url).status_code, 200)
        self.contract.status = Contract.Status.DRAFT
        self.contract.save()
        self.assertEqual(self.client.get(url).status_code, 410)

    def test_template_library_requires_staff(self):
        self.user.is_staff = False
        self.user.save(update_fields=("is_staff",))
        url = reverse("agency:template_library")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=("is_staff",))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_custom_client_form_creates_client_without_admin(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("agency:client_create"),
            {
                "trade_name": "Empresa Humana",
                "legal_name": "Empresa Humana LTDA",
                "tax_id": "",
                "kind": Client.Kind.SERVICE,
                "status": Client.Status.ACTIVE,
                "contact_name": "João",
                "email": "joao@example.com",
                "phone": "85999990000",
                "address": "Fortaleza - CE",
                "notes": "Cliente criado pelo fluxo personalizado.",
            },
        )
        created = Client.objects.get(trade_name="Empresa Humana")
        self.assertRedirects(response, reverse("agency:client_detail", kwargs={"pk": created.pk}))
        self.assertIsNone(created.tax_id)

    def test_custom_delivery_and_financial_forms_work(self):
        self.client.force_login(self.user)
        delivery_response = self.client.post(
            reverse("agency:delivery_create"),
            {
                "contract": self.contract.pk,
                "kind": DeliverableQuota.Kind.VIDEO,
                "title": "Vídeo institucional",
                "scheduled_for": "2026-09-18",
                "status": ContentDelivery.Status.PRODUCTION,
                "notes": "Roteiro aprovado.",
            },
        )
        self.assertRedirects(delivery_response, reverse("agency:delivery_list"))
        self.assertTrue(ContentDelivery.objects.filter(title="Vídeo institucional").exists())
        finance_response = self.client.post(
            reverse("agency:financial_entry_create"),
            {
                "kind": FinancialEntry.Kind.INCOME,
                "description": "Mensalidade setembro",
                "category": "Contratos",
                "amount": "1500.00",
                "due_date": "2026-09-10",
                "paid_date": "",
                "status": FinancialEntry.Status.PENDING,
                "client": self.client_record.pk,
                "contract": self.contract.pk,
                "notes": "",
            },
        )
        self.assertRedirects(finance_response, reverse("agency:finance"))
        self.assertTrue(FinancialEntry.objects.filter(description="Mensalidade setembro").exists())

    def test_financial_report_pdf_is_branded_pdf(self):
        FinancialEntry.objects.create(
            kind=FinancialEntry.Kind.INCOME,
            description="Receita do contrato",
            amount=Decimal("1500"),
            due_date=date(2026, 9, 10),
            status=FinancialEntry.Status.PENDING,
            client=self.client_record,
        )
        url = reverse("agency:financial_report_pdf") + "?month=2026-09"
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1000)
