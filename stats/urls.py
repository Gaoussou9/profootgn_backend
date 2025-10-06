# stats/urls.py
from django.urls import path
from .views import StandingsView, TopScorersView, PlayerTotalsView

urlpatterns = [
    path('standings/', StandingsView.as_view(), name='stats-standings'),
    path('topscorers/', TopScorersView.as_view(), name='stats-topscorers'),
    path("player-totals/", PlayerTotalsView.as_view(), name="player_totals"),
]
