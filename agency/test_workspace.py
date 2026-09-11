from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone

from .models import Client, Contract, ContentDelivery, FinancialEntry, TeamMember, Task, TaskChecklistItem, TaskComment, OrganizationSettings
from .work_forms import TeamMemberForm, OrganizationSettingsForm, TaskForm
from .forms import FinancialEntryForm


class WorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user('workspace-manager', is_staff=True)
        cls.worker = get_user_model().objects.create_user('workspace-worker')
        cls.finance_user = get_user_model().objects.create_user('workspace-finance')
        cls.member = TeamMember.objects.create(name='Equipe teste', user=cls.worker, role='production')
        TeamMember.objects.create(name='Financeiro teste', user=cls.finance_user, role='finance')
        cls.customer = Client.objects.create(trade_name='Cliente de teste')
        cls.contract = Contract.objects.create(client=cls.customer, title='Contrato de teste', start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30), monthly_value=Decimal('9876.54'), terms='Termos')
        cls.task = Task.objects.create(title='Pauta de teste', assignee=cls.member, client=cls.customer, due_date=timezone.localdate()-timedelta(days=1))

    def setUp(self):
        self.client.force_login(self.manager)

    def test_workspace_pages_render_with_data(self):
        for name in ('task_list', 'team_list', 'team_create', 'task_create', 'settings_edit'):
            self.assertEqual(self.client.get(reverse('agency:'+name)).status_code, 200, name)
        for view in ('kanban', 'list', 'calendar'):
            response = self.client.get(reverse('agency:task_list'), {'view': view})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, self.task.title)
        self.assertEqual(self.client.get(reverse('agency:task_detail', args=[self.task.pk])).status_code, 200)

    def test_roles_block_finance_contracts_team_and_settings(self):
        self.client.force_login(self.worker)
        for name in ('finance', 'financial_csv', 'financial_report_pdf', 'team_list', 'team_create', 'contract_list', 'contract_builder', 'settings_edit', 'template_library'):
            self.assertEqual(self.client.get(reverse('agency:'+name)).status_code, 403, name)
        dashboard = self.client.get(reverse('agency:dashboard'))
        self.assertNotContains(dashboard, 'Saldo realizado')
        customer = self.client.get(reverse('agency:client_detail', args=[self.customer.pk]))
        self.assertNotContains(customer, '9.876,54')
        self.assertEqual(self.client.post(reverse('agency:team_create'), {'name': 'Escalação', 'role':'manager'}).status_code, 403)
        self.client.force_login(self.finance_user)
        self.assertEqual(self.client.get(reverse('agency:finance')).status_code, 200)
        self.assertEqual(self.client.get(reverse('agency:team_list')).status_code, 403)

    def test_inactive_member_is_blocked_even_with_session(self):
        self.client.force_login(self.worker)
        TeamMember.objects.filter(pk=self.member.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse('agency:task_list')).status_code, 403)

    def test_task_status_is_post_only_and_has_conflict_protection(self):
        url = reverse('agency:task_status', args=[self.task.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {'status':'overdue'}).status_code, 400)
        version = self.task.updated_at.isoformat()
        response = self.client.post(url, {'status':'done','version':version}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_overdue)
        self.assertIsNotNone(self.task.completed_at)
        self.assertEqual(self.client.post(url, {'status':'doing','version':version}).status_code, 409)
        self.assertEqual(self.client.post(url, {'status':'doing','version':timezone.localtime(self.task.updated_at).isoformat()}).status_code, 302)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.completed_at)
        self.assertTrue(self.task.is_overdue)

    def test_status_requires_csrf(self):
        browser = TestClient(enforce_csrf_checks=True)
        browser.force_login(self.manager)
        self.assertEqual(browser.post(reverse('agency:task_status', args=[self.task.pk]), {'status':'done'}).status_code, 403)

    def test_checklist_comments_and_scope(self):
        url = reverse('agency:task_detail', args=[self.task.pk])
        self.client.post(url, {'action':'checklist','title':'Aprovar roteiro'})
        item = self.task.checklist.get()
        self.client.post(url, {'action':'check','item_id':item.pk,'done':'1'})
        item.refresh_from_db()
        self.assertTrue(item.is_done)
        other = Task.objects.create(title='Outra tarefa')
        foreign = TaskChecklistItem.objects.create(task=other,title='Outro item')
        self.assertEqual(self.client.post(url, {'action':'check','item_id':foreign.pk,'done':'1'}).status_code, 404)
        self.client.post(url, {'action':'comment','content':'<script>alert(1)</script>'})
        self.assertContains(self.client.get(url), '&lt;script&gt;')
        self.assertEqual(TaskComment.objects.get().author, self.manager)

    def test_task_filters_and_overdue_are_not_duplicated(self):
        response = self.client.get(reverse('agency:task_list'), {'assignee':self.member.pk})
        columns = response.context['columns']
        self.assertEqual(sum(len(c['items']) for c in columns), 1)
        self.assertEqual(columns[0]['items'][0].pk, self.task.pk)
        self.assertEqual(self.client.get(reverse('agency:task_list'), {'q':'missing'}).context['total'],0)
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse('agency:task_list'), {'assignee':'me'}).context['total'],1)

    def test_team_account_creation_and_deactivation(self):
        data={'name':'Nova pessoa','role':'production','is_active':'on','username':'nova-pessoa','password':'Portal-Test-Only!X93a'}
        form=TeamMemberForm(data)
        self.assertTrue(form.is_valid(),form.errors)
        member=form.save()
        self.assertTrue(member.user.check_password(data['password']))
        self.assertFalse(member.user.is_staff)
        data.update({'is_active':'','password':''})
        form=TeamMemberForm(data, instance=member)
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        member.user.refresh_from_db()
        self.assertFalse(member.user.is_active)
        duplicate=TeamMemberForm({'name':'Outra','role':'manager','username':'workspace-manager','password':'abc'})
        self.assertFalse(duplicate.is_valid())

    def test_paid_action_is_idempotent_and_cancelled_cannot_be_settled(self):
        entry=FinancialEntry.objects.create(kind='income',description='Recebimento',amount=100,due_date=timezone.localdate())
        url=reverse('agency:financial_settle',args=[entry.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.client.post(url)
        self.client.post(url)
        entry.refresh_from_db()
        self.assertEqual(entry.status,'paid')
        self.assertEqual(entry.paid_date,timezone.localdate())
        self.assertEqual(FinancialEntry.objects.count(),1)
        entry.status='cancelled'
        entry.save()
        self.client.post(url)
        entry.refresh_from_db()
        self.assertEqual(entry.status,'cancelled')

    def test_finance_cash_dates_categories_and_csv(self):
        today=timezone.localdate()
        FinancialEntry.objects.create(kind='income',description='=FORMULA',amount=1200,due_date=today-timedelta(days=40),paid_date=today,status='paid')
        FinancialEntry.objects.create(kind='expense',description='Equipe',category='Produção',amount=200,due_date=today,paid_date=today,status='paid')
        response=self.client.get(reverse('agency:finance'))
        self.assertEqual(response.context['realized_balance'],Decimal('1000'))
        self.assertEqual(response.context['category_rows'][0]['category'],'Produção')
        self.assertEqual(response.context['cash_rows'][0]['balance'],Decimal('1000'))
        FinancialEntry.objects.create(kind='income',description='=2+2',amount=10,due_date=today)
        self.assertContains(self.client.get(reverse('agency:financial_csv')), "'=2+2")
        for tab in ('summary','entries','cash'):
            self.assertEqual(self.client.get(reverse('agency:finance'),{'tab':tab}).status_code,200)

    def test_delivery_transition_sets_publication_and_filters_month(self):
        delivery=ContentDelivery.objects.create(contract=self.contract,title='Postagem',kind='feed',scheduled_for=timezone.localdate(),assignee=self.member)
        response=self.client.post(reverse('agency:delivery_status',args=[delivery.pk]),{'status':'published'})
        self.assertEqual(response.status_code,302)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.published_at)
        self.assertContains(self.client.get(reverse('agency:delivery_list'),{'assignee':self.member.pk}),delivery.title)
        self.assertNotContains(self.client.get(reverse('agency:delivery_list'),{'month':'2000-01'}),delivery.title)

    def test_organization_customization_validates_and_renders(self):
        data={'name':'Portal Personalizado','accent_color':'#902020','default_theme':'light','density':'compact','city':'Fortaleza','pdf_footer':'Comunicação'}
        form=OrganizationSettingsForm(data,instance=OrganizationSettings.current())
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        self.assertContains(self.client.get(reverse('agency:dashboard')),'Portal Personalizado')
        data['accent_color']='red; display:none'
        self.assertFalse(OrganizationSettingsForm(data).is_valid())
        self.assertEqual(self.client.get(reverse('brand_logo')).status_code,200)
        data['accent_color']='#123456'
        bad=SimpleUploadedFile('logo.svg',b'<svg><script/></svg>',content_type='image/svg+xml')
        self.assertFalse(OrganizationSettingsForm(data,{'logo':bad}).is_valid())

    def test_financial_contract_client_mismatch(self):
        other=Client.objects.create(trade_name='Outro cliente')
        form=FinancialEntryForm({'kind':'income','description':'Incorreto','amount':'10','due_date':timezone.localdate(),'status':'pending','client':other.pk,'contract':self.contract.pk})
        self.assertFalse(form.is_valid())
        self.assertIn('contract',form.errors)

    def test_contract_monthly_generation_is_idempotent_and_handles_short_months(self):
        from datetime import date
        self.contract.status='signed'
        self.contract.start_date=date(2026,1,1)
        self.contract.end_date=date(2026,12,31)
        self.contract.billing_day=31
        self.contract.save()
        url=reverse('agency:financial_generate')
        self.assertEqual(self.client.get(url).status_code,405)
        self.client.post(url,{'month':'2026-02'})
        self.client.post(url,{'month':'2026-02'})
        self.assertEqual(FinancialEntry.objects.count(),1)
        entry=FinancialEntry.objects.get()
        self.assertEqual(entry.due_date,date(2026,2,28))
        self.assertEqual(entry.amount,self.contract.monthly_value)
        self.assertEqual(entry.status,'pending')
