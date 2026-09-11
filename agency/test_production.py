from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Client, ContentDelivery, Contract, OrganizationSettings, Task, TeamMember


class ProductionWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('production-test-admin', password='Test-Only!9sQ7xy')
        cls.reader = get_user_model().objects.create_user('production-test-reader')
        cls.member = TeamMember.objects.create(user=cls.reader, name='Equipe teste', role='production', permissions={'tasks':'read','deliveries':'read'})
        customer = Client.objects.create(trade_name='Cliente unificado')
        today = timezone.localdate()
        contract = Contract.objects.create(client=customer, title='Pacote', start_date=today, end_date=today+timedelta(days=30), monthly_value=100)
        cls.delivery = ContentDelivery.objects.create(contract=contract, title='Material único', kind='story', scheduled_for=today, assignee=cls.member, status='production')
        cls.task = Task.objects.create(title='Tarefa única', due_date=today, client=customer, assignee=cls.member, status='doing')

    def test_combines_sources_and_all_three_views_without_writes(self):
        self.client.force_login(self.reader)
        for mode in ('kanban','list','calendar'):
            response = self.client.get(reverse('agency:production_workspace'), {'view':mode})
            self.assertContains(response, self.delivery.title)
            self.assertContains(response, self.task.title)
            self.assertNotContains(response, 'draggable="true"')
            self.assertEqual(response.context['total'], 2)
        self.assertEqual(ContentDelivery.objects.count(), 1)
        self.assertEqual(Task.objects.count(), 1)

    def test_permissions_never_leak_hidden_source(self):
        self.client.force_login(self.reader)
        TeamMember.objects.filter(pk=self.member.pk).update(permissions={'tasks':'none','deliveries':'read'})
        response = self.client.get(reverse('agency:production_workspace'))
        self.assertContains(response, self.delivery.title)
        self.assertNotContains(response, self.task.title)
        self.assertEqual(response.context['total'], 1)
        TeamMember.objects.filter(pk=self.member.pk).update(permissions={'tasks':'none','deliveries':'none'})
        self.assertEqual(self.client.get(reverse('agency:production_workspace')).status_code, 403)

    def test_filters_and_status_mapping_for_both_models(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('agency:production_workspace'))
        items = response.context['records']
        self.assertEqual({item['stage'] for item in items}, {'doing'})
        delivery = next(item for item in items if item['kind']=='delivery')
        task = next(item for item in items if item['kind']=='task')
        self.assertIn({'value':'published','label':'Publicado','stage':'done'}, delivery['status_choices'])
        self.assertIn({'value':'done','label':'Concluída','stage':'done'}, task['status_choices'])
        self.assertContains(response, 'data-board-status="done"')
        filtered = self.client.get(reverse('agency:production_workspace'), {'source':'delivery','assignee':str(self.member.pk),'q':'único'})
        self.assertEqual(filtered.context['total'],1)
        self.assertNotContains(filtered, self.task.title)

    def test_overdue_and_cancelled_not_duplicated(self):
        Task.objects.filter(pk=self.task.pk).update(due_date=timezone.localdate()-timedelta(days=2))
        ContentDelivery.objects.filter(pk=self.delivery.pk).update(status='cancelled',scheduled_for=timezone.localdate()-timedelta(days=2))
        self.client.force_login(self.admin)
        response = self.client.get(reverse('agency:production_workspace'))
        self.assertEqual(response.context['overdue_count'],1)
        self.assertEqual(sum(len(column['items']) for column in response.context['columns']),2)

    def test_dashboard_uses_portal_name_and_single_navigation_entry(self):
        OrganizationSettings.objects.update_or_create(pk=1, defaults={'name':'Portal Verdade Ceará'})
        self.client.force_login(self.admin)
        response = self.client.get(reverse('agency:dashboard'))
        self.assertContains(response, '<h1>Portal Verdade Ceará</h1>', html=True)
        self.assertNotContains(response, 'Olá,')
        self.assertContains(response, '<b>Produção e tarefas</b>', count=1, html=True)
        self.assertNotContains(response, '<b>Organização / tarefas</b>', html=True)
        self.assertNotContains(response, '<b>Materiais</b>', html=True)

    def test_admin_theme_does_not_remove_functional_controls(self):
        self.client.force_login(self.admin)
        for name,args in [('admin:index',[]),('admin:agency_client_changelist',[]),('admin:agency_client_add',[]),('admin:auth_user_change',[self.admin.pk])]:
            response=self.client.get(reverse(name,args=args))
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'css/admin_portal.css')
            self.assertContains(response,'CONTROLE DO SISTEMA')
        response=self.client.get(reverse('admin:agency_client_add'))
        self.assertContains(response,'csrfmiddlewaretoken')
        self.assertContains(response,'name="_save"')
