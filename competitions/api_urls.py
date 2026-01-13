from django.urls import path
from .api_views import (
    competitions_list_api,
    competition_matches_api,
)

app_name = "competitions_api"

urlpatterns = [
    path("competitions/", competitions_list_api),
    path("competitions/<int:competition_id>/matches/", competition_matches_api),
]
