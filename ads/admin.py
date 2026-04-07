from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import Ad, AdStat


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = (
        "ad_id",
        "title",
        "media_preview",
        "page",
        "position",
        "priority",  # ⭐ IMPORTANT
        "active",
        "impressions_count",
        "clicks_count",
        "created_at",
    )

    list_filter = (
        "active",
        "position",
        "page",
        "priority",  # ⭐ utile business
    )

    search_fields = ("ad_id", "title")

    readonly_fields = ("created_at", "media_preview")

    ordering = ("-created_at",)

    # 🔥 OPTIMISATION QUERY
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            impressions=Count("stats", filter=Q(stats__event="impression")),
            clicks=Count("stats", filter=Q(stats__event="click")),
        )

    # 📊 STATS
    def impressions_count(self, obj):
        return obj.impressions
    impressions_count.short_description = "Impressions"

    def clicks_count(self, obj):
        return obj.clicks
    clicks_count.short_description = "Clics"

    # 🖼️ IMAGE + 🎬 VIDEO PREVIEW
    def media_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.image.url)
        if obj.video:
            return format_html(
                '<video width="120" height="80" controls>'
                '<source src="{}" type="video/mp4"></video>',
                obj.video.url,
            )
        return "-"
    media_preview.short_description = "Preview"


@admin.register(AdStat)
class AdStatAdmin(admin.ModelAdmin):
    list_display = ("ad", "event", "ip", "created_at")

    list_filter = ("event", "created_at")

    readonly_fields = ("ad", "event", "ip", "user_agent", "created_at")

    ordering = ("-created_at",)