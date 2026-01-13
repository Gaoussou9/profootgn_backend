from rest_framework import serializers
from .models import Competition, CompetitionMatch


# =====================================================
# LISTE DES COMPÉTITIONS (API PUBLIQUE)
# =====================================================

class CompetitionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competition
        fields = [
            "id",
            "name",
            "slug",
        ]


# =====================================================
# MATCHS D’UNE COMPÉTITION
# =====================================================

class CompetitionMatchSerializer(serializers.ModelSerializer):
    home_team = serializers.SerializerMethodField()
    away_team = serializers.SerializerMethodField()
    status_label = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    class Meta:
        model = CompetitionMatch
        fields = [
            "id",
            "matchday",
            "datetime",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "status",
            "status_label",
        ]
        read_only_fields = [
            "id",
            "matchday",
            "datetime",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "status",
            "status_label",
        ]

    # =========================
    # TEAMS
    # =========================
    def get_home_team(self, obj):
        team = obj.home_team
        if not team:
            return None

        return {
            "id": team.id,
            "name": team.name,
            "logo": self._get_logo_url(team),
        }

    def get_away_team(self, obj):
        team = obj.away_team
        if not team:
            return None

        return {
            "id": team.id,
            "name": team.name,
            "logo": self._get_logo_url(team),
        }

    # =========================
    # UTILS
    # =========================
    def _get_logo_url(self, team):
        request = self.context.get("request")

        if team.logo and hasattr(team.logo, "url"):
            if request:
                return request.build_absolute_uri(team.logo.url)
            return team.logo.url

        return None
