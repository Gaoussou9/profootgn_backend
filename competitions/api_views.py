from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Competition, CompetitionMatch, CompetitionTeam
from .serializers import (
    CompetitionMatchSerializer,
    CompetitionListSerializer,
)
from .services.standings import calculate_competition_standings


# =====================================================
# LISTE DES COMPÉTITIONS
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
# MATCHS D’UNE COMPÉTITION
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
            "season": competition.season,
        },
        "matches": serializer.data
    })


# =====================================================
# CLASSEMENT (AVEC FORM + PENALTY)
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
            "penalty_points": row.get("penalty_points", 0),
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
# CLUBS
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
    )

    clubs = []

    for club in teams:
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
# DETAIL CLUB (AVEC STATS AJOUTÉES)
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

    # 🔥 On récupère le classement pour trouver les stats du club
    table = calculate_competition_standings(competition)

    stats_data = None
    position = 1

    for row in table:
        if row["team"].id == club.id:
            stats_data = {
                "position": position,
                "played": row["played"],
                "wins": row["wins"],
                "draws": row["draws"],
                "losses": row["losses"],
                "goal_difference": row["goal_difference"],
                "points": row["points"],
            }
            break
        position += 1

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
            "city": club.city,
        },
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "stats": stats_data
    })


# =====================================================
# MATCHS D’UN CLUB
# =====================================================

@api_view(["GET"])
def competition_club_matches_api(request, competition_id, club_id):
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

    matches = (
        CompetitionMatch.objects
        .filter(competition=competition)
        .filter(Q(home_team=club) | Q(away_team=club))
        .select_related("home_team", "away_team")
        .order_by("-datetime")
    )

    serializer = CompetitionMatchSerializer(
        matches,
        many=True,
        context={"request": request}
    )

    return Response(serializer.data)


# =====================================================
# DÉTAIL D’UN MATCH
# =====================================================

@api_view(["GET"])
def competition_match_detail(request, competition_id, match_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    match = get_object_or_404(
        CompetitionMatch,
        id=match_id,
        competition=competition
    )

    serializer = CompetitionMatchSerializer(
        match,
        context={"request": request}
    )

    return Response(serializer.data)


# =====================================================
# JOUEURS D’UN CLUB
# =====================================================

@api_view(["GET"])
def competition_club_players_api(request, competition_id, club_id):
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

    players = club.players.filter(is_active=True).order_by("number")

    data = []

    for player in players:
        data.append({
            "id": player.id,
            "name": player.name,
            "number": player.number,
            "position": player.position,
            "photo": (
                request.build_absolute_uri(player.photo.url)
                if getattr(player, "photo", None)
                else None
            ),
        })

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "club": {
            "id": club.id,
            "name": club.name,
        },
        "players": data
    })
