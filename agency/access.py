from django.core.exceptions import PermissionDenied

from .models import TeamMember, OrganizationSettings


def capabilities(user):
    member = getattr(user, "team_member", None)
    manager = user.is_authenticated and (user.is_superuser or user.is_staff or bool(member and member.is_active and member.role == TeamMember.Role.MANAGER))
    finance = manager or bool(member and member.is_active and member.role == TeamMember.Role.FINANCE)
    return {"can_manage": manager, "can_finance": finance, "portal_member": member}


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
        if member and not member.is_active:
            raise PermissionDenied
        name = match.url_name
        if (name.startswith("financial") or name == "finance") and not access["can_finance"]:
            raise PermissionDenied
        if name == "financial_generate" and not access["can_manage"]:
            raise PermissionDenied
        if (name.startswith("settings_") or name.startswith("team_") or name.startswith("template_") or name.startswith("contract_")) and not access["can_manage"]:
            raise PermissionDenied
