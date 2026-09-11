from django.core.exceptions import PermissionDenied

from .models import TeamMember, OrganizationSettings


MODULES = {"clients": "Clientes", "contracts": "Contratos e modelos (inclui valores)",
           "deliveries": "Materiais", "tasks": "Tarefas e Kanban", "finance": "Financeiro e relatórios"}
LEVELS = [("", "Seguir perfil"), ("none", "Sem acesso"), ("read", "Somente visualizar"), ("write", "Visualizar e editar")]


def capabilities(user):
    member = getattr(user, "team_member", None)
    authenticated = bool(user.is_authenticated and user.is_active)
    active = authenticated and (not member or member.is_active or user.is_superuser)
    # Team profiles cannot grant staff/superuser or delegate access.
    admin = active and (user.is_superuser or (user.is_staff and not member))
    manager = active and (admin or bool(member and member.role == TeamMember.Role.MANAGER))
    defaults = {key: "none" for key in MODULES}
    if active and (admin or member):
        defaults.update(clients="write", deliveries="write", tasks="write")
        if manager:
            defaults.update(contracts="write", finance="write")
        elif member.role == TeamMember.Role.FINANCE:
            defaults["finance"] = "write"
    overrides = member.permissions if member and isinstance(member.permissions, dict) else {}
    levels = {key: "write" if admin else overrides.get(key, default) if active else "none"
              for key, default in defaults.items()}
    access = {"can_manage": manager, "can_manage_users": admin,
              "can_customize": manager, "portal_member": member}
    for key, level in levels.items():
        access[f"can_view_{key}"] = level in ("read", "write")
        access[f"can_edit_{key}"] = level == "write"
    access["can_finance"] = access["can_view_finance"]
    return access


def access_context(request):
    return {**capabilities(request.user), "organization": OrganizationSettings.current()}


class PortalAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if not request.user.is_authenticated or not match or match.namespace != "agency":
            return
        access = capabilities(request.user)
        member = access["portal_member"]
        if member and not member.is_active and not request.user.is_superuser:
            raise PermissionDenied
        name = match.url_name
        if name.startswith("team_") and not access["can_manage_users"]:
            raise PermissionDenied
        if name.startswith("settings_") and not access["can_customize"]:
            raise PermissionDenied
        module = next((module for prefix, module in (
            ("client_", "clients"), ("contract_", "contracts"), ("template_", "contracts"),
            ("delivery_", "deliveries"), ("task_", "tasks"), ("financ", "finance")) if name.startswith(prefix)), None)
        if module:
            editing = request.method not in ("GET", "HEAD", "OPTIONS") or name.endswith(("_create", "_edit", "_builder", "_status", "_settle", "_generate"))
            if not access[f"can_{'edit' if editing else 'view'}_{module}"]:
                raise PermissionDenied("Seu acesso não permite esta operação. Consulte o administrador.")
