from rest_framework import serializers
from django.utils import timezone
from .models import Competition, CompetitionMatch, Player, Goal, Card


# =====================================================
# LISTE DES COMPÉTITIONS
# =====================================================

class CompetitionListSerializer(serializers.ModelSerializer):

    logo = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = [
            "id",
            "name",
            "slug",
            "season",
            "logo",
        ]

    def get_logo(self, obj):
        request = self.context.get("request")

        if obj.logo and hasattr(obj.logo, "url"):
            url = obj.logo.url
            return request.build_absolute_uri(url) if request else url

        return None


# =====================================================
# 🔥 GOALS
# =====================================================

class GoalSerializer(serializers.ModelSerializer):

    player_name = serializers.CharField(source="player.name", read_only=True)
    assist_name = serializers.CharField(source="assist_player.name", read_only=True)

    player_photo = serializers.SerializerMethodField()

    team = serializers.SerializerMethodField()

    club_id = serializers.IntegerField(source="team.id", read_only=True)
    player_id = serializers.IntegerField(source="player.id", read_only=True)

    goal_type = serializers.CharField(
    source="type",
    read_only=True
)

    goal_type_label = serializers.CharField(
    source="get_type_display",
    read_only=True
)

    class Meta:
        model = Goal
        fields = [
            "id",
            "minute",

            "goal_type",
            "goal_type_label",

            "team",

            "player_name",
            "assist_name",
            "player_photo",

            "club_id",
            "player_id",
        ]

    def get_team(self, obj):
        return obj.team.id if obj.team else None

    def get_player_photo(self, obj):
        request = self.context.get("request")

        if obj.player and obj.player.photo:
            url = obj.player.photo.url
            return request.build_absolute_uri(url) if request else url

        return None
# =====================================================
# 🔥 CARDS
# =====================================================

class CardSerializer(serializers.ModelSerializer):

    player_name = serializers.CharField(source="player.name", read_only=True)
    player_photo = serializers.SerializerMethodField()
    reason_label = serializers.CharField(source="get_reason_display", read_only=True)
    team = serializers.SerializerMethodField()  # ✅ ICI
    club_id = serializers.IntegerField(source="team.id", read_only=True)
    player_id = serializers.IntegerField(source="player.id", read_only=True)
    

    class Meta:
        model = Card
        fields = [
            "id",
            "minute",
            "color",
            "reason",
            "reason_label",
            "team",  # ✅ ICI
            "player_name",
            "player_photo",
            "club_id",
            "player_id",
        ]

    def get_team(self, obj):
        return obj.team.id if obj.team else None

    def get_player_photo(self, obj):
        request = self.context.get("request")
        if obj.player and obj.player.photo:
            url = obj.player.photo.url
            return request.build_absolute_uri(url) if request else url
        return None
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

    minute = serializers.SerializerMethodField()

    # 🔥 AJOUT IMPORTANT
    goals = GoalSerializer(many=True, read_only=True)
    cards = CardSerializer(many=True, read_only=True)

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
            "phase_start",
            "phase_offset",
            "minute",

            # 🔥 AJOUT
            "goals",
            "cards",
        ]

    # ===============================
    # ÉQUIPES
    # ===============================

    def get_home_team(self, obj):
        return self.serialize_team(obj.home_team)

    def get_away_team(self, obj):
        return self.serialize_team(obj.away_team)

    def serialize_team(self, team):

        if not team:
            return {
                "id": None,
                "name": None,
                "logo": None
            }

        request = self.context.get("request")

        logo = None
        if team.logo and hasattr(team.logo, "url"):
            logo_url = team.logo.url
            logo = request.build_absolute_uri(logo_url) if request else logo_url

        return {
            "id": team.id,
            "name": team.name,
            "logo": logo,
        }

    # ===============================
    # MINUTE LIVE
    # ===============================

    def get_minute(self, obj):

        if obj.status == "HT":
            return 45

        if obj.status != "LIVE":
            return None

        seconds = obj.phase_offset or 0

        if obj.phase_start:
            delta = timezone.now() - obj.phase_start
            seconds += int(delta.total_seconds())

        return seconds // 60


# =====================================================
# JOUEURS
# =====================================================

class PlayerSerializer(serializers.ModelSerializer):

    photo = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = [
            "id",
            "name",
            "number",
            "position",
            "photo",
            "age",
            "nationality",
            "height",
            "previous_club_1",
            "previous_club_2",
            "previous_club_3",

            # 📊 STATS
            "matches_played",
            "goals",
            "assists",
            "yellow_cards",
            "red_cards",

            "club",
        ]

    def get_photo(self, obj):

        request = self.context.get("request")

        if obj.photo and hasattr(obj.photo, "url"):
            url = obj.photo.url
            return request.build_absolute_uri(url) if request else url

        return None