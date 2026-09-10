from django.contrib import admin

from .models import Client, ContentDelivery, Contract, ContractTemplate, DeliverableQuota, FinancialEntry


class DeliverableQuotaInline(admin.TabularInline):
    model = DeliverableQuota
    extra = 1


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("trade_name", "kind", "status", "contact_name", "phone", "updated_at")
    list_filter = ("kind", "status")
    search_fields = ("trade_name", "legal_name", "tax_id", "contact_name", "email", "phone")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "template", "start_date", "end_date", "monthly_value", "status", "signed_at")
    list_filter = ("status", "template", "start_date", "end_date")
    search_fields = ("title", "client__trade_name", "client__legal_name")
    readonly_fields = ("signature_token", "signed_at", "signature_ip", "signature_user_agent", "signature_hash")
    inlines = (DeliverableQuotaInline,)


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "content")


@admin.register(ContentDelivery)
class ContentDeliveryAdmin(admin.ModelAdmin):
    list_display = ("title", "contract", "kind", "scheduled_for", "status")
    list_filter = ("kind", "status", "scheduled_for")
    search_fields = ("title", "contract__client__trade_name")
    date_hierarchy = "scheduled_for"


@admin.register(FinancialEntry)
class FinancialEntryAdmin(admin.ModelAdmin):
    list_display = ("description", "kind", "amount", "due_date", "status", "client")
    list_filter = ("kind", "status", "due_date", "category")
    search_fields = ("description", "client__trade_name", "category")
    date_hierarchy = "due_date"
