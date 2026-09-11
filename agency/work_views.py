import calendar

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ContentDelivery, TeamMember, Task, TaskChecklistItem, TaskComment, Client, OrganizationSettings
from .work_forms import TeamMemberForm, TaskForm, OrganizationSettingsForm


@login_required
def settings_form(request):
    form = OrganizationSettingsForm(request.POST or None, request.FILES or None, instance=OrganizationSettings.current())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Personalização salva. Novos contratos podem utilizar os dados da empresa pelas variáveis do modelo.")
        return redirect("agency:settings_edit")
    return render(request, "agency/entity_form.html", {"form": form, "title": "Personalize seu Portal", "eyebrow": "Configurações da empresa", "description": "Ajuste identidade visual, tamanho da interface e dados do papel timbrado. Preferências de tema escolhidas no navegador prevalecem sobre o tema padrão.", "back_url": reverse("agency:dashboard"), "submit_label": "Salvar configurações"})


@login_required
def help_page(request):
    return render(request, "agency/help.html")


def brand_logo(request):
    from django.http import FileResponse
    from django.conf import settings
    from pathlib import Path
    organization = OrganizationSettings.current()
    if organization.logo:
        try:
            return FileResponse(organization.logo.open("rb"))
        except FileNotFoundError:
            pass
    return FileResponse((Path(settings.BASE_DIR) / "static/images/logo-portal-verdade-ceara.png").open("rb"), content_type="image/png")


@login_required
def team_list(request):
    members = TeamMember.objects.select_related("user").annotate(
        open_tasks=Count("tasks", filter=~Q(tasks__status=Task.Status.DONE)),
        done_tasks=Count("tasks", filter=Q(tasks__status=Task.Status.DONE)),
        late_tasks=Count("tasks", filter=Q(tasks__due_date__lt=timezone.localdate()) & ~Q(tasks__status=Task.Status.DONE)),
    )
    return render(request, "agency/team_list.html", {"members": members, "active_count": members.filter(is_active=True).count()})


@login_required
def team_form(request, pk=None):
    member = get_object_or_404(TeamMember.objects.select_related("user"), pk=pk) if pk else None
    if member and member.user_id and (member.user.is_staff or member.user.is_superuser or member.user_id == request.user.pk):
        raise PermissionDenied("O próprio acesso e contas administrativas são gerenciados nas configurações avançadas.")
    form = TeamMemberForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Integrante salvo. O acesso segue o perfil e a situação definidos.")
        return redirect("agency:team_list")
    return render(request, "agency/entity_form.html", {"form": form, "title": "Editar integrante" if member else "Novo integrante", "eyebrow": "Equipe & permissões", "description": "Gestão: acesso completo. Financeiro: caixa, clientes e operação. Produção: clientes, materiais e tarefas.", "back_url": reverse("agency:team_list"), "submit_label": "Salvar integrante"})


@login_required
def task_list(request):
    from .views import requested_month, month_bounds
    tasks = Task.objects.select_related("assignee", "client").prefetch_related("checklist")
    query = request.GET.get("q", "").strip()
    assignee = request.GET.get("assignee", "")
    priority = request.GET.get("priority", "")
    if query:
        tasks = tasks.filter(Q(title__icontains=query) | Q(client__trade_name__icontains=query))
    if assignee.isdigit():
        tasks = tasks.filter(assignee_id=int(assignee))
    elif assignee == "me":
        tasks = tasks.filter(assignee__user=request.user)
    elif assignee == "none":
        tasks = tasks.filter(assignee__isnull=True)
    if priority in Task.Priority.values:
        tasks = tasks.filter(priority=priority)
    view = request.GET.get("view", "kanban")
    if view not in ("kanban", "list", "calendar"):
        view = "kanban"
    month = requested_month(request)
    all_tasks = list(tasks)
    overdue = [item for item in all_tasks if item.is_overdue]
    columns = [{"key": "overdue", "label": "Atrasadas", "items": overdue}]
    columns += [{"key": key, "label": label, "items": [item for item in all_tasks if item.status == key and not item.is_overdue]} for key, label in Task.Status.choices]
    weeks = []
    if view == "calendar":
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
            weeks.append([{"date": day, "current": day.month == month.month, "today": day == timezone.localdate(), "items": [t for t in all_tasks if t.due_date == day]} for day in week])
    tab_links = {}
    for key in ("kanban", "list", "calendar"):
        params = request.GET.copy()
        params["view"] = key
        tab_links[key] = "?" + params.urlencode()
    return render(request, "agency/task_list.html", {"tasks": all_tasks, "columns": columns, "view_mode": view, "weeks": weeks, "month_value": month.strftime("%Y-%m"), "query": query, "selected_assignee": assignee, "selected_priority": priority, "members": TeamMember.objects.all(), "priority_choices": Task.Priority.choices, "status_choices": Task.Status.choices, "tab_links": tab_links, "total": len(all_tasks), "overdue_count": len(overdue), "doing_count": sum(t.status in (Task.Status.DOING, Task.Status.REVIEW) for t in all_tasks), "done_count": sum(t.status == Task.Status.DONE for t in all_tasks), "undated_count": sum(t.due_date is None for t in all_tasks)})


@login_required
def task_form(request, pk=None):
    task = get_object_or_404(Task, pk=pk) if pk else None
    form = TaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        instance = form.save(commit=False)
        if not instance.pk:
            instance.created_by = request.user
        instance.save()
        messages.success(request, "Tarefa salva com sucesso.")
        return redirect("agency:task_detail", pk=instance.pk)
    return render(request, "agency/entity_form.html", {"form": form, "title": "Editar tarefa" if task else "Nova tarefa", "eyebrow": "Organização / tarefas", "description": "Defina o objetivo, o responsável e o prazo. Adicione checklist e comentários após salvar.", "back_url": reverse("agency:task_list"), "submit_label": "Salvar tarefa"})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task.objects.select_related("assignee", "client", "delivery").prefetch_related("checklist", "comments__author"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "comment":
            content = request.POST.get("content", "").strip()
            if not content or len(content) > 3000:
                messages.error(request, "Informe um comentário entre 1 e 3.000 caracteres.")
            else:
                TaskComment.objects.create(task=task, author=request.user, content=content)
                messages.success(request, "Comentário adicionado.")
        elif action == "checklist":
            title = request.POST.get("title", "").strip()
            if not title or len(title) > 200:
                messages.error(request, "Informe um item de até 200 caracteres.")
            else:
                TaskChecklistItem.objects.create(task=task, title=title)
        elif action == "check":
            item_id = request.POST.get("item_id", "")
            item = get_object_or_404(TaskChecklistItem, pk=int(item_id) if item_id.isdigit() else 0, task=task)
            item.is_done = request.POST.get("done") == "1"
            item.save(update_fields=["is_done"])
        else:
            messages.error(request, "Ação não reconhecida.")
        return redirect("agency:task_detail", pk=pk)
    checklist = list(task.checklist.all())
    return render(request, "agency/task_detail.html", {"task": task, "checklist": checklist, "checklist_done": sum(item.is_done for item in checklist), "status_choices": Task.Status.choices})


@login_required
@require_POST
@transaction.atomic
def task_status(request, pk):
    task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
    new_status = request.POST.get("status")
    if new_status not in Task.Status.values:
        return JsonResponse({"error": "Etapa inválida. Atrasos são calculados pelo prazo."}, status=400)
    version = request.POST.get("version")
    if version and version != task.updated_at.isoformat() and version != timezone.localtime(task.updated_at).isoformat():
        return JsonResponse({"error": "Esta tarefa foi alterada por outra pessoa. Atualize o quadro."}, status=409)
    task.status = new_status
    task.save()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": task.status, "version": task.updated_at.isoformat()})
    return redirect("agency:task_detail", pk=pk)


@login_required
@require_POST
@transaction.atomic
def delivery_status(request, pk):
    item = get_object_or_404(ContentDelivery.objects.select_for_update(), pk=pk)
    status = request.POST.get("status")
    if status not in ContentDelivery.Status.values:
        return JsonResponse({"error": "Etapa inválida."}, status=400)
    version = request.POST.get("version")
    if version and version != item.updated_at.isoformat() and version != timezone.localtime(item.updated_at).isoformat():
        return JsonResponse({"error": "Este material foi alterado. Atualize o quadro."}, status=409)
    item.status = status
    item.published_at = (item.published_at or timezone.now()) if status == ContentDelivery.Status.PUBLISHED else None
    item.save()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": item.status, "version": item.updated_at.isoformat()})
    return redirect("agency:delivery_list")
