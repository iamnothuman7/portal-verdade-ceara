import calendar
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_safe

from .access import capabilities
from .models import ContentDelivery, Task, TeamMember


DELIVERY_STAGES = {'planned': 'todo', 'production': 'doing', 'approval': 'review', 'published': 'done', 'cancelled': 'cancelled'}
STAGES = [('todo', 'Planejamento'), ('doing', 'Em execução'), ('review', 'Em revisão'), ('done', 'Concluídos'), ('cancelled', 'Cancelados')]


@login_required
@require_safe
def workspace(request, source_filter='all'):
    access = capabilities(request.user)
    if not (access['can_view_tasks'] or access['can_view_deliveries']):
        raise PermissionDenied
    source = request.GET.get('source', source_filter)
    if source not in ('all', 'task', 'delivery'):
        source = 'all'
    mode = request.GET.get('view', 'kanban')
    if mode not in ('kanban', 'list', 'calendar'):
        mode = 'kanban'
    query = request.GET.get('q', '').strip()
    assignee = request.GET.get('assignee', '')
    priority = request.GET.get('priority', '')
    from .views import requested_month, month_bounds
    month = requested_month(request)
    month_value = request.GET.get('month', '')
    has_month = bool(month_value) or mode == 'calendar'
    start, end = month_bounds(month)
    today = timezone.localdate()
    records = []
    for kind, allowed, model, customer_lookup, date_field in (
        ('task', access['can_view_tasks'], Task, 'client__trade_name', 'due_date'),
        ('delivery', access['can_view_deliveries'], ContentDelivery, 'contract__client__trade_name', 'scheduled_for'),
    ):
        if not allowed or source not in ('all', kind):
            continue
        queryset = model.objects.all()
        if kind == 'task':
            queryset = queryset.select_related('client', 'assignee').prefetch_related('checklist')
            if priority in Task.Priority.values:
                queryset = queryset.filter(priority=priority)
        else:
            queryset = queryset.select_related('contract__client', 'assignee')
            if priority in Task.Priority.values and priority != 'normal':
                continue
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(**{customer_lookup+'__icontains': query}))
        if assignee.isdigit():
            queryset = queryset.filter(assignee_id=int(assignee))
        elif assignee == 'me':
            queryset = queryset.filter(assignee__user=request.user)
        elif assignee == 'none':
            queryset = queryset.filter(assignee__isnull=True)
        if has_month:
            date_query = Q(**{date_field+'__gte': start, date_field+'__lt': end})
            if kind == 'task':
                date_query |= Q(due_date__isnull=True)
            queryset = queryset.filter(date_query)
        for obj in queryset:
            task = kind == 'task'
            due = obj.due_date if task else obj.scheduled_for
            stage = obj.status if task else DELIVERY_STAGES[obj.status]
            can_edit = access['can_edit_tasks' if task else 'can_edit_deliveries']
            checklist = list(obj.checklist.all()) if task else []
            choices = Task.Status.choices if task else ContentDelivery.Status.choices
            records.append({
                'uid': f'{kind}-{obj.pk}', 'kind': kind, 'kind_label': 'Tarefa' if task else obj.get_kind_display(),
                'title': obj.title, 'client': obj.client if task else obj.contract.client,
                'assignee': obj.assignee, 'due_date': due, 'stage': stage, 'status': obj.status,
                'status_label': obj.get_status_display(), 'priority': obj.priority if task else 'normal',
                'priority_label': obj.get_priority_display() if task else 'Normal',
                'is_overdue': bool(due and due < today and stage not in ('done', 'cancelled')),
                'detail_url': reverse('agency:task_detail', args=[obj.pk]) if task else reverse('agency:delivery_edit', args=[obj.pk]) if can_edit else '',
                'can_edit': can_edit, 'status_url': reverse('agency:task_status' if task else 'agency:delivery_status', args=[obj.pk]),
                'version': obj.updated_at.isoformat(), 'checklist_total': len(checklist),
                'checklist_done': sum(item.is_done for item in checklist),
                'status_choices': [{'value': value, 'label': label, 'stage': value if task else DELIVERY_STAGES[value]} for value, label in choices],
            })
    records.sort(key=lambda item: (item['due_date'] or date.max, item['title'].casefold(), item['uid']))
    overdue = [item for item in records if item['is_overdue']]
    columns = [{'key': 'overdue', 'label': 'Atrasados', 'items': overdue}]
    columns += [{'key': key, 'label': label, 'items': [item for item in records if item['stage'] == key and not item['is_overdue']]} for key, label in STAGES if key != 'cancelled' or any(item['stage'] == key for item in records)]
    weeks = []
    if mode == 'calendar':
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
            weeks.append([{'date': day, 'current': day.month == month.month, 'today': day == today, 'items': [item for item in records if item['due_date'] == day]} for day in week])
    links = {}
    for value in ('kanban', 'list', 'calendar'):
        params = request.GET.copy()
        params['source'] = source
        params['view'] = value
        links[value] = '?' + params.urlencode()
    return render(request, 'agency/production_workspace.html', {
        'records': records, 'columns': columns, 'weeks': weeks, 'view_mode': mode, 'tab_links': links,
        'query': query, 'selected_assignee': assignee, 'selected_priority': priority, 'selected_source': source,
        'month_value': month.strftime('%Y-%m') if has_month else '', 'members': TeamMember.objects.all(),
        'priority_choices': Task.Priority.choices, 'total': len(records), 'overdue_count': len(overdue),
        'doing_count': sum(item['stage'] in ('doing', 'review') for item in records),
        'done_count': sum(item['stage'] == 'done' for item in records), 'undated_count': sum(item['due_date'] is None for item in records),
    })
