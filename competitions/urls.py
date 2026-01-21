# competitions/urls.py
from django.urls import path
from .views import competition_matches_view
from .api_views import (
    competition_matches_api,
    competitions_list_api,
    competition_clubs_api,
    competition_club_detail_api,
)
from .api_views import competition_standings_api
from .api_views import competition_club_detail_api

app_name = "competitions"

urlpatterns = [
    # =========================
    # ADMIN UI
    # =========================
    path(
        "<int:competition_id>/matches/",
        competition_matches_view,
        name="competition_matches",
    ),
    path(
    "api/competitions/<int:competition_id>/clubs/<int:club_id>/",
    competition_club_detail_api,
    name="competition-club-detail",
        ),

    # =========================
    # API PUBLIQUE
    # =========================
    path(
        "api/competitions/",
        competitions_list_api,
        name="api_competitions_list",
    ),
    path(
        "api/competitions/<int:competition_id>/matches/",
        competition_matches_api,
        name="api_competition_matches",
    ),

    path(
    "api/competitions/<int:competition_id>/standings/",
    competition_standings_api,
    name="api_competition_standings",
),
path(
    "api/competitions/<int:competition_id>/clubs/",
    competition_clubs_api,
    name="api_competition_clubs",
),


    path(
        "api/competitions/<int:competition_id>/clubs/<int:club_id>/",
        competition_club_detail_api,
        name="api_competition_club_detail",
    ),
]