import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .access import MODULES, capabilities
from .models import Client, Contract, ContentDelivery, OrganizationSettings, Task, TeamMember
from .work_forms import OrganizationSettingsForm, TeamMemberForm


class AccessBrandingTests(TestCase):
    def test_brand_logos_revalidate_without_resending_identical_images(self):
        for name in ("brand_logo", "brand_compact_logo", "brand_panel_logo"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            etag = response["ETag"]
            response.close()
            cached = self.client.get(reverse(name), HTTP_IF_NONE_MATCH=etag)
            self.assertEqual(cached.status_code, 304)
            self.assertEqual(cached["ETag"], etag)
            self.assertEqual(cached["Cache-Control"], "no-cache")

    def test_panel_logo_cache_changes_when_brand_variant_changes(self):
        organization = OrganizationSettings.current()
        organization.save()
        original = self.client.get(reverse("brand_panel_logo"))
        etag = original["ETag"]
        original.close()
        organization.panel_logo = "compact"
        organization.save(update_fields=["panel_logo"])
        changed = self.client.get(reverse("brand_panel_logo"), HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(changed.status_code, 200)
        self.assertNotEqual(changed["ETag"], etag)
        changed.close()

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("access-test-admin", password="Test-Only!9sQ7xy")
        cls.reader = get_user_model().objects.create_user("access-test-reader", password="Test-Only!9sQ7xy")
        cls.member = TeamMember.objects.create(name="Leitor", user=cls.reader, role="production",
                                              permissions={key: "read" for key in MODULES})
        cls.customer = Client.objects.create(trade_name="Cliente confidencial")
        cls.contract = Contract.objects.create(client=cls.customer, title="Contrato reservado", monthly_value=100,
                                              start_date=timezone.localdate(), end_date=timezone.localdate(), terms="Texto")
        cls.task = Task.objects.create(title="Tarefa reservada")
        cls.delivery = ContentDelivery.objects.create(title="Material reservado", contract=cls.contract,
                                                     kind="feed", scheduled_for=timezone.localdate())

    def test_read_only_routes_and_downloads(self):
        self.client.force_login(self.reader)
        for route in ("client_list", "contract_list", "template_library", "delivery_list", "task_list", "finance", "financial_csv", "financial_report_pdf"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse("agency:" + route)).status_code, 200)
        response = self.client.get(reverse("agency:contract_detail", args=[self.contract.pk]))
        self.assertNotContains(response, str(self.contract.signature_token))
        self.assertEqual(self.client.get(reverse("agency:contract_pdf", args=[self.contract.pk])).status_code, 200)

    def test_read_only_blocks_all_writes_and_edit_screens(self):
        self.client.force_login(self.reader)
        routes = [("client_create", []), ("client_edit", [self.customer.pk]), ("contract_builder", []),
                  ("contract_edit", [self.contract.pk]), ("template_create", []), ("delivery_create", []),
                  ("delivery_edit", [self.delivery.pk]), ("delivery_status", [self.delivery.pk]),
                  ("task_create", []), ("task_edit", [self.task.pk]), ("task_status", [self.task.pk]),
                  ("financial_entry_create", []), ("financial_entry_edit", [1]), ("financial_generate", []),
                  ("financial_settle", [1]), ("team_create", []), ("settings_edit", [])]
        for name, args in routes:
            with self.subTest(route=name):
                url = reverse("agency:" + name, args=args)
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {"status": "done", "is_superuser": "on"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("agency:task_detail", args=[self.task.pk]),
                                         {"action": "comment", "content": "Denied"}).status_code, 403)
        self.assertFalse(self.task.comments.exists())

    def test_read_only_ui_preserves_titles_but_hides_edit_controls(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse("agency:delivery_list"))
        self.assertContains(response, self.delivery.title)
        self.assertNotContains(response, 'draggable="true"')
        self.assertNotContains(response, ">Mover</button>")
        self.assertNotContains(response, "+ Novo material")
        response = self.client.get(reverse("agency:task_detail", args=[self.task.pk]))
        self.assertNotContains(response, "Editar tarefa")
        self.assertNotContains(response, 'class="comment-form"')
        self.assertNotContains(self.client.get(reverse("agency:finance")), "+ Novo lançamento")

    def test_denied_modules_do_not_leak_dashboard_data(self):
        TeamMember.objects.filter(pk=self.member.pk).update(permissions={key: "none" for key in MODULES})
        self.client.force_login(self.reader)
        response = self.client.get(reverse("agency:dashboard"))
        for text in (self.delivery.title, self.task.title, "Saldo realizado", "Clientes ativos", "Contratos vigentes"):
            self.assertNotContains(response, text)
        for route in ("client_list", "contract_list", "task_list", "delivery_list", "financial_csv", "financial_report_pdf"):
            self.assertEqual(self.client.get(reverse("agency:" + route)).status_code, 403)

    def test_grant_specific_module_and_no_administrative_escalation(self):
        TeamMember.objects.filter(pk=self.member.pk).update(permissions={"finance": "write"}, role="manager")
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse("agency:financial_entry_create")).status_code, 200)
        self.assertEqual(self.client.post(reverse("agency:team_create"), {"role": "manager"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_superuser_cannot_be_locked_out_by_team_overrides(self):
        TeamMember.objects.create(name="Administrador", user=self.admin, is_active=False,
                                  permissions={key: "none" for key in MODULES})
        self.client.force_login(self.admin)
        for route in ("team_create", "settings_edit", "financial_entry_create", "contract_builder"):
            self.assertEqual(self.client.get(reverse("agency:" + route)).status_code, 200)

    def test_create_credentials_permissions_and_safe_audit(self):
        self.client.force_login(self.admin)
        data = {"name": "Integrante teste", "username": "scoped-test-user", "password": "Test-Only!6gR8xp",
                "role": "production", "is_active": "on", "access_finance": "read", "access_tasks": "none",
                "is_staff": "on", "is_superuser": "on", "permissions": '{"team":"write"}'}
        self.assertRedirects(self.client.post(reverse("agency:team_create"), data), reverse("agency:team_list"))
        member = TeamMember.objects.get(user__username="scoped-test-user")
        self.assertEqual(member.permissions, {"finance": "read", "tasks": "none"})
        self.assertTrue(member.user.check_password(data["password"]))
        self.assertFalse(member.user.is_staff)
        self.assertFalse(member.user.is_superuser)
        audit = LogEntry.objects.get(object_id=str(member.pk))
        self.assertNotIn(data["password"], audit.change_message)
        self.assertEqual(audit.user, self.admin)
        self.assertEqual(self.client.get(reverse("admin:agency_teammember_history", args=[member.pk])).status_code, 200)

    def test_password_reset_invalidates_session_and_disable_blocks_login(self):
        self.client.force_login(self.reader)
        data = {"name": "Leitor", "username": self.reader.username, "password": "Test-Only!6gR8xp",
                "role": "production", "is_active": "on"}
        form = TeamMemberForm(data, instance=self.member)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(self.client.get(reverse("agency:dashboard")).status_code, 302)
        self.assertTrue(self.client.login(username=self.reader.username, password=data["password"]))
        data.update(password="", is_active="")
        form = TeamMemberForm(data, instance=self.member)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(self.client.get(reverse("agency:dashboard")).status_code, 302)
        self.assertFalse(self.client.login(username=self.reader.username, password="Test-Only!6gR8xp"))

    def test_invalid_permission_is_rejected_and_plain_account_is_unprivileged(self):
        form = TeamMemberForm({"name": "Teste", "role": "production", "access_finance": "root"})
        self.assertFalse(form.is_valid())
        orphan = get_user_model().objects.create_user("no-profile")
        self.assertFalse(any(capabilities(orphan)[f"can_view_{key}"] for key in MODULES))

    def test_logo_selection_fallback_and_documents_keep_full_logo(self):
        self.client.force_login(self.admin)
        data = {"name": "Portal", "city": "Fortaleza / CE", "accent_color": "#c71927", "default_theme": "dark", "density": "compact", "panel_logo": "compact"}
        self.assertRedirects(self.client.post(reverse("agency:settings_edit"), data), reverse("agency:settings_edit"))
        self.assertEqual(OrganizationSettings.current().panel_logo, "compact")
        self.assertContains(self.client.get(reverse("agency:dashboard")), 'sidebar-brand logo-compact')
        compact = self.client.get(reverse("brand_panel_logo"))
        self.assertEqual(b"".join(compact.streaming_content), (Path(settings.BASE_DIR) / "static/images/favicon-portal.png").read_bytes())
        full = self.client.get(reverse("brand_logo"))
        self.assertEqual(b"".join(full.streaming_content), (Path(settings.BASE_DIR) / "static/images/logo-portal-verdade-ceara.png").read_bytes())
        self.assertEqual(compact["Cache-Control"], "no-cache")

    def test_custom_compact_upload_validation_and_clear(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            content = BytesIO()
            Image.new("RGB", (32, 32), "red").save(content, format="PNG")
            data = {"name": "Portal", "city": "Fortaleza / CE", "accent_color": "#c71927", "default_theme": "dark", "density": "compact", "panel_logo": "compact"}
            form = OrganizationSettingsForm(data, {"compact_logo": SimpleUploadedFile("symbol.png", content.getvalue(), content_type="image/png")}, instance=OrganizationSettings.current())
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
            response = self.client.get(reverse("brand_panel_logo"))
            self.assertEqual(b"".join(response.streaming_content), content.getvalue())
            form = OrganizationSettingsForm({**data, "compact_logo-clear": "on"}, instance=OrganizationSettings.current())
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
            self.assertFalse(OrganizationSettings.current().compact_logo)
            bad = OrganizationSettingsForm(data, {"compact_logo": SimpleUploadedFile("fake.png", b"<script>x</script>", content_type="image/png")})
            self.assertFalse(bad.is_valid())
