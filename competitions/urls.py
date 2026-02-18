from django.urls import path
from .views import competition_matches_view
from .api_views import (
    competitions_list_api,
    competition_matches_api,
    competition_clubs_api,
    competition_club_detail_api,
    competition_club_matches_api,
    competition_standings_api,
    competition_club_players_api,
    competition_match_detail,
)
from competitions.admin_views import admin_competition_clubs

app_name = "competitions"

urlpatterns = [
    # =========================
    # ADMIN UI
    # =========================
    path(
        "admin/competitions/<int:competition_id>/clubs/",
        admin_competition_clubs,
        name="admin-competition-clubs",
    ),

    path(
        "<int:competition_id>/matches/",
        competition_matches_view,
        name="competition_matches",
    ),

    # =========================
    # API PUBLIQUE
    # =========================

    # Liste compétitions
    path(
        "api/competitions/",
        competitions_list_api,
        name="api_competitions_list",
    ),

    # Matchs d'une compétition
    path(
        "api/competitions/<int:competition_id>/matches/",
        competition_matches_api,
        name="api_competition_matches",
    ),

    # ✅ DÉTAIL MATCH COMPÉTITION (CORRIGÉ ICI)
    path(
        "api/competitions/<int:competition_id>/matches/<int:match_id>/",
        competition_match_detail,
        name="api_competition_match_detail",
    ),

    # Classement
    path(
        "api/competitions/<int:competition_id>/standings/",
        competition_standings_api,
        name="api_competition_standings",
    ),

    # Clubs
    path(
        "api/competitions/<int:competition_id>/clubs/",
        competition_clubs_api,
        name="api_competition_clubs",
    ),

    # Détail club
    path(
        "api/competitions/<int:competition_id>/clubs/<int:club_id>/",
        competition_club_detail_api,
        name="api_competition_club_detail",
    ),

    # Matchs d'un club
    path(
        "api/competitions/<int:competition_id>/clubs/<int:club_id>/matches/",
        competition_club_matches_api,
        name="api_competition_club_matches",
    ),

    # Joueurs d'un club
    path(
        "api/competitions/<int:competition_id>/clubs/<int:club_id>/players/",
        competition_club_players_api,
        name="api_competition_club_players",
    ),
]
