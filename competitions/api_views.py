from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Competition, CompetitionMatch, CompetitionTeam
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
                    if getattr(team, "logo", None)
                    else None
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


# =====================================================
# CLUBS D’UNE COMPÉTITION
# =====================================================

@api_view(["GET"])
def competition_clubs_api(request, competition_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    teams = CompetitionTeam.objects.filter(
        competition=competition,
        is_active=True
    ).order_by("id")

    clubs = []

    for ct in teams:
        """
        ⚠️ IMPORTANT
        CompetitionTeam n’a PAS de champ `team`
        → on utilise ce qui existe réellement
        """

        # Cas 1 : CompetitionTeam → club
        club = ct.club if hasattr(ct, "club") else ct

        clubs.append({
            "id": club.id,
            "name": club.name,
            "logo": (
                request.build_absolute_uri(club.logo.url)
                if getattr(club, "logo", None)
                else None
            ),
        })

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "clubs": clubs
    })

# =====================================================
# DÉTAIL D’UN CLUB (SAFE JSON)
# =====================================================

@api_view(["GET"])
def competition_club_detail_api(request, competition_id, club_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    club = get_object_or_404(
        CompetitionTeam,
        id=club_id,
        competition=competition,
        is_active=True
    )

    return Response({
        "id": club.id,
        "name": club.name,
        "short_name": club.short_name,
        "logo": (
            request.build_absolute_uri(club.logo.url)
            if club.logo else None
        ),
        "city": club.city,
        "penalties": club.penalties,

        # ✅ VALEURS SIMPLES SEULEMENT
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },

        # ✅ STATS SIMPLES (PAS DE RelatedManager)
        "stats": {
            "matches_played": club.home_matches.count() + club.away_matches.count(),
            "home_matches": club.home_matches.count(),
            "away_matches": club.away_matches.count(),
        }
    })
# =====================================================
# DÉTAIL D’UN CLUB DANS UNE COMPÉTITION
# =====================================================

@api_view(["GET"])
def competition_club_detail_api(request, competition_id, club_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    # ⚠️ Le club DOIT appartenir à cette compétition
    club = get_object_or_404(
        CompetitionTeam,
        competition=competition,
        id=club_id,
        is_active=True
    )

    # Calcul du classement pour récupérer les stats du club
    table = calculate_competition_standings(competition)

    club_stats = None

    for row in table:
        if row["team"].id == club.id:
            club_stats = row
            break

    if not club_stats:
        return Response(
            {"error": "Stats du club introuvables"},
            status=404
        )

    return Response({
        "club": {
            "id": club.id,
            "name": club.name,
            "short_name": club.short_name,
            "logo": (
                request.build_absolute_uri(club.logo.url)
                if getattr(club, "logo", None)
                else None
            ),
            "city": getattr(club, "city", None),
        },
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "stats": {
            "position": table.index(club_stats) + 1,
            "played": club_stats["played"],
            "wins": club_stats["wins"],
            "draws": club_stats["draws"],
            "losses": club_stats["losses"],
            "goals_for": club_stats["goals_for"],
            "goals_against": club_stats["goals_against"],
            "goal_difference": club_stats["goal_difference"],
            "points": club_stats["points"],
            "penalty_points": club_stats["penalty_points"],
            "form": club_stats.get("form", []),
        }
    })
