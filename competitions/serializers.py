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


    # =========================
    # TEAMS (FORMAT STABLE FRONT)
    # =========================
    def get_home_team(self, obj):
        return self._serialize_team(obj.home_team)

    def get_away_team(self, obj):
        return self._serialize_team(obj.away_team)


    # =========================
    # UTILS
    # =========================
    def _serialize_team(self, team):
        """
        Format unique pour une équipe
        → React peut afficher même si logo ou team est null
        """
        if not team:
            return {
                "id": None,
                "name": None,
                "logo": None,
            }

        return {
            "id": team.id,
            "name": team.name,
            "logo": self._get_logo_url(team),
        }

    def _get_logo_url(self, team):
        request = self.context.get("request")

        if team.logo and hasattr(team.logo, "url"):
            if request:
                return request.build_absolute_uri(team.logo.url)
            return team.logo.url

        return None
