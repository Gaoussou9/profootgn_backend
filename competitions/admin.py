from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Competition,
    CompetitionTeam,
    CompetitionMatch,
    CompetitionPenalty,
)

# =====================================================
# UTIL : LOGO PREVIEW
# =====================================================

def team_logo(team, size=26):
    """
    Affiche le logo + nom d'une équipe de compétition
    """
    if not team:
        return "—"

    if team.logo:
        return format_html(
            '<img src="{}" style="height:{}px;vertical-align:middle;margin-right:6px;" />{}',
            team.logo.url,
            size,
            team.name,
        )

    return team.name


# =====================================================
# INLINE : ÉQUIPES DE LA COMPÉTITION
# =====================================================

class CompetitionTeamInline(admin.TabularInline):
    model = CompetitionTeam
    extra = 1

    fields = (
        "logo_preview",
        "name",
        "short_name",
        "city",
        "coach",
        "is_active",
    )

    readonly_fields = ("logo_preview",)
    show_change_link = True

    verbose_name = "Équipe de la compétition"
    verbose_name_plural = "Équipes de la compétition"

    def logo_preview(self, obj):
        return team_logo(obj, size=22)

    logo_preview.short_description = "Logo"


# =====================================================
# INLINE : PÉNALITÉS DE POINTS
# =====================================================

class CompetitionPenaltyInline(admin.TabularInline):
    model = CompetitionPenalty
    extra = 0

    fields = (
        "team",
        "points",
        "reason",
        "created_at",
    )

    readonly_fields = ("created_at",)
    autocomplete_fields = ("team",)

    verbose_name = "Pénalité de points"
    verbose_name_plural = "Pénalités de points"


# =====================================================
# ADMIN : COMPÉTITION
# =====================================================

@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "season",
        "type",
        "category",
        "is_active",
        "priority",
        "manage_matches",
    )

    list_filter = ("type", "category", "season", "is_active")
    search_fields = ("name", "short_name")
    prepopulated_fields = {"slug": ("name",)}

    inlines = [
        CompetitionTeamInline,
        CompetitionPenaltyInline,
    ]

    def manage_matches(self, obj):
        url = reverse(
            "competitions:competition_matches",
            args=[obj.id]
        )
        return format_html(
            '<a class="button" href="{}">Gérer les matchs</a>',
            url
        )

    manage_matches.short_description = "Matchs"


# =====================================================
# ADMIN : ÉQUIPE DE COMPÉTITION
# =====================================================

@admin.register(CompetitionTeam)
class CompetitionTeamAdmin(admin.ModelAdmin):
    list_display = (
        "logo_preview",
        "name",
        "competition",
        "city",
        "coach",
        "is_active",
    )

    list_filter = ("competition", "is_active")
    search_fields = ("name", "competition__name")
    autocomplete_fields = ("competition",)

    readonly_fields = ("logo_preview",)

    def logo_preview(self, obj):
        return team_logo(obj)

    logo_preview.short_description = "Logo"


# =====================================================
# ADMIN : MATCH DE COMPÉTITION
# =====================================================

@admin.register(CompetitionMatch)
class CompetitionMatchAdmin(admin.ModelAdmin):
    list_display = (
        "competition",
        "matchday",
        "home_team_display",
        "score",
        "away_team_display",
        "status",
        "datetime",
    )

    list_filter = (
        "competition",
        "status",
    )

    search_fields = (
        "home_team__name",
        "away_team__name",
        "competition__name",
    )

    ordering = ("matchday", "datetime")
    readonly_fields = ("competition",)

    def home_team_display(self, obj):
        return team_logo(obj.home_team)

    def away_team_display(self, obj):
        return team_logo(obj.away_team)

    def score(self, obj):
        return f"{obj.home_score} - {obj.away_score}"

    home_team_display.short_description = "Domicile"
    away_team_display.short_description = "Extérieur"
    score.short_description = "Score"


# =====================================================
# ADMIN : PÉNALITÉS (ACCÈS DIRECT)
# =====================================================

@admin.register(CompetitionPenalty)
class CompetitionPenaltyAdmin(admin.ModelAdmin):
    list_display = (
        "competition",
        "team",
        "points",
        "reason",
        "created_at",
    )

    list_filter = ("competition",)
    search_fields = ("team__name", "competition__name", "reason")
    autocomplete_fields = ("competition", "team")
    readonly_fields = ("created_at",)
