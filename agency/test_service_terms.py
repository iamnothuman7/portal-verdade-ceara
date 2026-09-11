from importlib import import_module
from datetime import date
from django.apps import apps
from django.test import TestCase
from django.utils import timezone
from .models import Client, Contract, ContractTemplate
from .forms import ContractBuilderForm, add_calendar_months, contract_duration


class ServiceTermsTests(TestCase):
    def test_terms_preserve_custom_text_and_issued_contracts_and_are_idempotent(self):
        migration = import_module("agency.migrations.0009_service_materials_and_visits_terms")
        template = ContractTemplate.objects.get(name=migration.TEMPLATE_NAME)
        template.content = "Condição comercial personalizada que deve ser preservada."
        template.save()
        customer = Client.objects.create(trade_name="Cliente teste cláusulas")
        contract = Contract.objects.create(client=customer, title="Contrato emitido", start_date=timezone.localdate(),
            end_date=timezone.localdate(), monthly_value=100, terms="Termos originais assinados", status="signed", signed_at=timezone.now())
        migration.update_service_terms(apps, None)
        migration.update_service_terms(apps, None)
        template.refresh_from_db()
        contract.refresh_from_db()
        self.assertIn("Condição comercial personalizada que deve ser preservada.", template.content)
        self.assertEqual(template.content.count(migration.MATERIALS_HEADING), 1)
        self.assertEqual(template.content.count(migration.VISITS_HEADING), 1)
        self.assertEqual(template.content.count(migration.TERMINATION_HEADING), 1)
        self.assertEqual(contract.terms, "Termos originais assinados")

    def test_seeded_template_contains_operational_terms_and_company_variables(self):
        template = ContractTemplate.objects.get(name="Prestação de serviços de comunicação")
        for text in ("Stories", "Collabs", "logomarca", "não serão repostos", "CONTRATADO deverá informar", "[[empresa_documento]]", "30 (trinta) dias", "10% (dez por cento)", "5 (cinco) dias úteis", "[[prazo_contrato]]"):
            self.assertIn(text, template.content)
        rendered = template.render({"empresa_documento": "DOCUMENTO DE TESTE"})
        self.assertIn("DOCUMENTO DE TESTE", rendered)

    def test_default_six_months_and_end_of_month_dates(self):
        form = ContractBuilderForm()
        self.assertEqual(form.initial['end_date'], add_calendar_months(form.initial['start_date'], 6))
        self.assertEqual(add_calendar_months(date(2026, 8, 31), 6), date(2027, 2, 28))
        self.assertEqual(contract_duration(date(2026, 8, 31), date(2027, 2, 28)), '6 (seis) meses')
        self.assertEqual(contract_duration(date(2026, 9, 11), date(2026, 10, 11)), '1 mês')
        self.assertEqual(contract_duration(date(2026, 9, 11), date(2026, 9, 26)), '15 dias')

    def test_builder_renders_selected_dates_without_fixed_six_month_contradiction(self):
        customer = Client.objects.create(trade_name='Cliente teste vigência')
        template = ContractTemplate.objects.get(name='Prestação de serviços de comunicação')
        data = dict(client=customer.pk, template=template.pk, title='Divulgação', start_date='2026-09-11', end_date='2027-03-11', monthly_value='100.00', billing_day=10, status='draft')
        form = ContractBuilderForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertIn('prazo determinado de 6 (seis) meses', contract.terms)
        self.assertNotIn('[[', contract.terms)
        data['end_date'] = '2026-12-11'
        form = ContractBuilderForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertIn('prazo determinado de 3 meses', contract.terms)
        self.assertNotIn('6 (seis)', contract.terms)
