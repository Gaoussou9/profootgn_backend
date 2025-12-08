from django.contrib import admin
from .models import Ad, AdStat

@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ("ad_id","title","active","created_at")
    search_fields = ("ad_id","title")

@admin.register(AdStat)
class AdStatAdmin(admin.ModelAdmin):
    list_display = ("ad","event","ip","created_at")
    list_filter = ("event","created_at")
    readonly_fields = ("ip","user_agent","created_at")
    ordering = ("-created_at",)
