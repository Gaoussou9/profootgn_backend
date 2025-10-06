# matches/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# DRF (API publique / actions .py)
from . import views as api

# ========= Admin rapides: import tolérant =========
# On tente d'abord admin_views.py, sinon on retombe sur views.py si les fonctions y sont définies.
quick_add_match_view = quick_events = quick_events_api = quick_lineups = quick_lineups_api = None
try:
    from .admin_views import (
        quick_add_match_view as _q_match,
        quick_events as _q_events,
        quick_events_api as _q_events_api,
        quick_lineups as _q_lineups,
        quick_lineups_api as _q_lineups_api,
    )
    quick_add_match_view = _q_match
    quick_events = _q_events
    quick_events_api = _q_events_api
    quick_lineups = _q_lineups
    quick_lineups_api = _q_lineups_api
except Exception:
    # fallback: si les vues admin sont dans views.py
    quick_add_match_view = getattr(api, "admin_quick_match", None)
    quick_events        = getattr(api, "admin_quick_events", None)
    quick_events_api    = getattr(api, "admin_quick_events_api", None)
    quick_lineups       = getattr(api, "admin_quick_lineups", None)
    quick_lineups_api   = getattr(api, "admin_quick_lineups_api", None)

_HAS_ADMIN_VIEWS = all([
    quick_add_match_view is not None,
    quick_events is not None,
    quick_events_api is not None,
    quick_lineups is not None,
    quick_lineups_api is not None,
])

app_name = "matches"

# ========= Router DRF avec enregistrement sûr =========
router = DefaultRouter()

def _safe_register(prefix, viewset_attr, basename):
    vs = getattr(api, viewset_attr, None)
    if vs is not None:
        try:
            router.register(prefix, vs, basename=basename)
        except Exception:
            # on ignore si la classe n'est pas un ViewSet valide
            pass

_safe_register(r"matches", "MatchViewSet", "match")
_safe_register(r"goals",   "GoalViewSet",   "goal")
_safe_register(r"cards",   "CardViewSet",   "card")
_safe_register(r"rounds",  "RoundViewSet",  "round")
_safe_register(r"lineups", "LineupViewSet", "lineup")  # CRUD lineups (admin/public)

urlpatterns = [
    # API REST (DRF)
    path("", include(router.urls)),

    # Endpoints compatibles avec le front
    path("matches/<int:pk>/lineups/",   api.match_lineups,   name="match_lineups"),     # GET: liste (avec rating)
    path("matches/<int:pk>/team-info/", api.match_team_info, name="match_team_info"),   # GET|PUT: formation/coach

    # Actions "boutons" admin .py
    path("ajouter.py",   api.ajouter_match,   name="ajouter_match"),
    path("modifier.py",  api.modifier_match,  name="modifier_match"),
    path("supprimer.py", api.supprimer_match, name="supprimer_match"),
    path("suspendre.py", api.suspendre_match, name="suspendre_match"),

    # Stats & recherche
    path("stats/standings/",          api.standings_view,    name="standings"),
    path("stats/assists-leaders/",    api.assists_leaders,   name="assists_leaders"),  # ⬅️ AJOUT
    path("players/search/",           api.search_players,    name="players_search"),
    path("clubs/<int:club_id>/players-stats/", api.club_players_stats, name="club_players_stats"),
]

# ========= Routes admin rapides (HTML + API JSON) =========
if _HAS_ADMIN_VIEWS:
    urlpatterns += [
        path("admin/quick/",         quick_add_match_view, name="admin_quick_match"),
        path("admin/events/",        quick_events,         name="admin_quick_events"),
        path("admin/lineups/quick/", quick_lineups,        name="admin_quick_lineups"),
        path("admin/events/api/",    quick_events_api,     name="admin_quick_events_api"),
        path("admin/lineups/api/",   quick_lineups_api,    name="admin_quick_lineups_api"),
    ]
