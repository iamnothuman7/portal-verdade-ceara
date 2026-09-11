from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .forms import StyledModelForm
from .models import TeamMember, Task, ContentDelivery, OrganizationSettings
from .access import MODULES, LEVELS


class OrganizationSettingsForm(StyledModelForm):
    class Meta:
        model = OrganizationSettings
        fields = ("name", "legal_name", "tax_id", "email", "phone", "address", "city", "accent_color", "default_theme", "density", "panel_logo", "logo", "compact_logo", "pdf_footer")
        widgets = {"accent_color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["panel_logo"].required = False
        self.fields["logo"].help_text = "Marca inteira para o painel, login e documentos. Sem envio, será usada a marca original."
        self.fields["compact_logo"].help_text = "Símbolo para o painel compacto. Sem envio, será usado o símbolo original."

    def clean_panel_logo(self):
        return self.cleaned_data.get("panel_logo") or self.instance.panel_logo or "full"

    def _clean_brand_image(self, field):
        logo = self.cleaned_data.get(field)
        if logo and hasattr(logo, "content_type"):
            if logo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("A imagem deve ter até 5 MB.")
            if logo.content_type not in ("image/png", "image/jpeg", "image/webp"):
                raise forms.ValidationError("Use uma imagem PNG, JPEG ou WebP.")
            if logo.image.width * logo.image.height > 25_000_000:
                raise forms.ValidationError("A imagem deve ter no máximo 25 megapixels.")
        return logo

    def clean_logo(self):
        return self._clean_brand_image("logo")

    def clean_compact_logo(self):
        return self._clean_brand_image("compact_logo")


class TeamMemberForm(StyledModelForm):
    username = forms.CharField(label="Usuário de acesso (opcional)", max_length=150, required=False,
                               help_text="Deixe vazio para cadastrar apenas como responsável, sem acesso ao sistema.")
    password = forms.CharField(label="Senha de acesso", required=False, strip=False, widget=forms.PasswordInput,
                               help_text="Obrigatória para criar um acesso. Ao editar, deixe em branco para manter a senha.")

    class Meta:
        model = TeamMember
        fields = ("name", "job_title", "email", "phone", "role", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, label in MODULES.items():
            overrides = self.instance.permissions or {}
            self.fields[f"access_{key}"] = forms.ChoiceField(label=label, choices=LEVELS, required=False,
                initial=overrides.get(key, ""), widget=forms.Select(attrs={"class": "studio-input"}))
        if self.instance.user_id:
            self.fields["username"].initial = self.instance.user.username
            self.fields["username"].disabled = True

    def clean_username(self):
        username = self.cleaned_data["username"]
        if username and not self.instance.user_id:
            for validator in get_user_model()._meta.get_field("username").validators:
                validator(username)
            if get_user_model().objects.filter(username__iexact=username).exists():
                raise forms.ValidationError("Este usuário já existe. Escolha outro nome.")
        return username

    def clean(self):
        data = super().clean()
        username, password = data.get("username"), data.get("password")
        if username and not self.instance.user_id and not password:
            self.add_error("password", "Defina uma senha para criar o acesso.")
        if password and not username:
            self.add_error("username", "Informe o usuário para habilitar o acesso.")
        if password:
            user = get_user_model()(username=username or "", first_name=data.get("name", ""), email=data.get("email", ""))
            try:
                validate_password(password, user)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return data

    @transaction.atomic
    def save(self, commit=True):
        member = super().save(commit=False)
        member.permissions = {key: self.cleaned_data[f"access_{key}"] for key in MODULES if self.cleaned_data.get(f"access_{key}")}
        if self.cleaned_data.get("username"):
            user = member.user if member.user_id else get_user_model()(username=self.cleaned_data["username"])
            user.first_name = member.name[:150]
            user.email = member.email
            user.is_active = member.is_active
            if self.cleaned_data.get("password"):
                user.set_password(self.cleaned_data["password"])
            if commit:
                user.save()
                member.user = user
        if commit:
            member.save()
        return member

    @property
    def identity_fields(self):
        return [field for field in self if not field.name.startswith("access_")]

    @property
    def permission_fields(self):
        return [self[f"access_{key}"] for key in MODULES]


class TaskForm(StyledModelForm):
    class Meta:
        model = Task
        fields = ("title", "description", "priority", "status", "due_date", "assignee", "client", "delivery")
        widgets = {"description": forms.Textarea(attrs={"rows": 4}), "due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = TeamMember.objects.filter(is_active=True) | TeamMember.objects.filter(pk=self.instance.assignee_id)
        self.fields["delivery"].queryset = ContentDelivery.objects.select_related("contract__client")
