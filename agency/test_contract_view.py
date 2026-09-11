from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Client, Contract, ContractTemplate, DeliverableQuota, TeamMember
from .pdf import build_contract_pdf


class ContractViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('viewer-admin', password='Test-Only!9sQ7xy')
        cls.reader = get_user_model().objects.create_user('viewer-reader', password='Test-Only!9sQ7xy')
        cls.member = TeamMember.objects.create(user=cls.reader, name='Leitor', role='production', permissions={'contracts': 'read'})
        cls.customer = Client.objects.create(trade_name='Cliente de teste')
        cls.contract = Contract.objects.create(client=cls.customer, title='Contrato enviado de teste', status='sent', terms='Condições preservadas do documento enviado.', start_date=date(2026, 9, 11), end_date=date(2027, 3, 11), monthly_value=600)

    def test_requires_login_and_contract_read_permission(self):
        url = reverse('agency:contract_view', args=[self.contract.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(url).status_code, 200)
        TeamMember.objects.filter(pk=self.member.pk).update(permissions={'contracts': 'none'})
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_read_only_preserves_sent_terms_and_hides_signing_token(self):
        self.client.force_login(self.reader)
        ContractTemplate.objects.all().update(content='Modelo alterado depois do envio')
        before = Contract.objects.values().get(pk=self.contract.pk)
        response = self.client.get(reverse('agency:contract_view', args=[self.contract.pk]))
        self.assertContains(response, self.contract.terms)
        self.assertContains(response, 'somente leitura')
        self.assertContains(response, reverse('agency:contract_pdf', args=[self.contract.pk]))
        for text in ('Modelo alterado depois do envio', 'Assinar contrato', '<form', str(self.contract.signature_token)):
            self.assertNotContains(response, text)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(before, Contract.objects.values().get(pk=self.contract.pk))
        self.assertContains(self.client.get(reverse('agency:contract_list')), 'Ver contrato enviado')
        self.assertContains(self.client.get(reverse('agency:contract_detail', args=[self.contract.pk])), 'Ver contrato enviado')

    def test_cannot_post_even_as_administrator(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('agency:contract_view', args=[self.contract.pk]), {'consent': 'on', 'signer_name': 'Não assinar'})
        self.assertEqual(response.status_code, 405)
        self.contract.refresh_from_db()
        self.assertIsNone(self.contract.signed_at)

    def test_signed_proof_visible_without_public_token(self):
        Contract.objects.filter(pk=self.contract.pk).update(status='signed', signed_at=timezone.now(), signer_name='Signatário de teste', signature_hash='a' * 64)
        self.client.force_login(self.reader)
        response = self.client.get(reverse('agency:contract_view', args=[self.contract.pk]))
        self.assertContains(response, 'Comprovante da assinatura')
        self.assertContains(response, 'Signatário de teste')
        self.assertNotContains(response, str(self.contract.signature_token))
        self.assertContains(self.client.get(reverse('agency:contract_list')), 'Ver contrato assinado')

    def test_pdf_handles_long_notes_without_changing_contract(self):
        DeliverableQuota.objects.create(contract=self.contract, kind='story', quantity=12, notes='Observações extensas com <caracteres> e & símbolos. ' * 80)
        before = Contract.objects.values().get(pk=self.contract.pk)
        result = build_contract_pdf(self.contract)
        self.assertTrue(result.startswith(b'%PDF'))
        self.assertEqual(before, Contract.objects.values().get(pk=self.contract.pk))
