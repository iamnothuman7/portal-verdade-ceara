from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .forms import StyledModelForm
from .models import TeamMember, Task, ContentDelivery, OrganizationSettings


class OrganizationSettingsForm(StyledModelForm):
    class Meta:
        model = OrganizationSettings
        fields = ("name", "legal_name", "tax_id", "email", "phone", "address", "city", "accent_color", "default_theme", "density", "logo", "pdf_footer")
        widgets = {"accent_color": forms.TextInput(attrs={"type": "color"})}

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "content_type"):
            if logo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("A imagem deve ter até 5 MB.")
            if logo.content_type not in ("image/png", "image/jpeg", "image/webp"):
                raise forms.ValidationError("Use uma imagem PNG, JPEG ou WebP.")
            if logo.image.width * logo.image.height > 25_000_000:
                raise forms.ValidationError("A imagem deve ter no máximo 25 megapixels.")
        return logo


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


class TaskForm(StyledModelForm):
    class Meta:
        model = Task
        fields = ("title", "description", "priority", "status", "due_date", "assignee", "client", "delivery")
        widgets = {"description": forms.Textarea(attrs={"rows": 4}), "due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = TeamMember.objects.filter(is_active=True) | TeamMember.objects.filter(pk=self.instance.assignee_id)
        self.fields["delivery"].queryset = ContentDelivery.objects.select_related("contract__client")
