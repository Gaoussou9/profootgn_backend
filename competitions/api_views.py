from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Competition, CompetitionMatch
from .serializers import (
    CompetitionMatchSerializer,
    CompetitionListSerializer,
)

from .services.standings import calculate_competition_standings


# =====================================================
# LISTE DES COMPÉTITIONS (API PUBLIQUE)
# =====================================================

@api_view(["GET"])
def competitions_list_api(request):
    competitions = (
        Competition.objects
        .filter(is_active=True)
        .order_by("priority", "name")
    )

    serializer = CompetitionListSerializer(
        competitions,
        many=True,
        context={"request": request}
    )
    return Response(serializer.data)


# =====================================================
# MATCHS D’UNE COMPÉTITION (AVEC INFOS COMPÉTITION)
# =====================================================

@api_view(["GET"])
def competition_matches_api(request, competition_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    matches = (
        CompetitionMatch.objects
        .filter(competition=competition)
        .select_related("home_team", "away_team")
        .order_by("matchday", "datetime")
    )

    serializer = CompetitionMatchSerializer(
        matches,
        many=True,
        context={"request": request}
    )

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "short_name": competition.short_name,
            "season": competition.season,
            "type": competition.type,
            "category": competition.category,
        },
        "matches": serializer.data
    })


# =====================================================
# CLASSEMENT D’UNE COMPÉTITION (AVEC FORME LIVE)
# =====================================================

@api_view(["GET"])
def competition_standings_api(request, competition_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    table = calculate_competition_standings(competition)

    standings = []
    position = 1

    for row in table:
        team = row["team"]

        standings.append({
            "position": position,
            "team": {
                "id": team.id,
                "name": team.name,
                "logo": (
                    request.build_absolute_uri(team.logo.url)
                    if team.logo else None
                ),
            },
            "played": row["played"],
            "wins": row["wins"],
            "draws": row["draws"],
            "losses": row["losses"],
            "goals_for": row["goals_for"],
            "goals_against": row["goals_against"],
            "goal_difference": row["goal_difference"],
            "points": row["points"],
            "penalty_points": row["penalty_points"],

            # 🔥 FORME RÉELLE (V / N / D)
            "form": row.get("form", []),
        })

        position += 1

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "standings": standings
    })
