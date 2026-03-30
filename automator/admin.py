from django.contrib import admin
from .models import ShopifyAccount, AutomationLog

@admin.register(ShopifyAccount)
class ShopifyAccountAdmin(admin.ModelAdmin):
	list_display = ("email", "phone", "created_at")

@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
	list_display = ("timestamp", "message")
