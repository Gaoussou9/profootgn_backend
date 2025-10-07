# profootgn/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.static import serve  # pour exposer /media/ en prod

# ===== Admin rapides (matches / events / lineups) =====
from matches.admin_views import (
    quick_add_match_view,
    quick_events,
    quick_events_api,
    quick_lineups,       # éditeur rapide des compos
    quick_lineups_api,   # API admin pour les compos
)

# ===== Admin rapides (players) =====
from players.admin_views import (
    quick_add_players_view,
    admin_players_by_club,  # JSON: joueurs d'un club (utilisé par la page compos)
)

# ===== Admin rapides (clubs) =====
from clubs.admin_views import (
    quick_clubs,
    quick_roster,
    quick_clubs_api,        # API admin clubs
)

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def root_ping(request):
    return JsonResponse({
        "name": "ProFootGN API",
        "admin": "/admin/",
        "auth": {
            "token": "/api/auth/token/",
            "refresh": "/api/auth/token/refresh/",
        },
        "endpoints": [
            "/api/",
            "/api/matches/",
            "/api/matches/<id>/",
            "/api/matches/<id>/lineups/",
            "/api/matches/<id>/team-info/",
            "/api/lineups/",
            "/api/goals/", "/api/cards/", "/api/rounds/",
            "/api/stats/",
            "/api/players/search/",
            "/admin/matches/quick/",
            "/admin/events/quick/",
            "/admin/lineups/quick/",
            "/admin/clubs/quick/",
            "/admin/clubs/quick/<id>/",
            "/admin/clubs/quick/api/",
            "/admin/lineups/api/",
            "/admin/clubs/<club_id>/players/",
        ],
    })


urlpatterns = [
    path("", root_ping, name="root"),

    # ✅ Health check simple pour Render et monitoring
    path("api/health/", lambda r: JsonResponse({"status": "ok"})),

    # ===== Admin custom (pages rapides) =====
    path("admin/matches/quick/",  admin.site.admin_view(quick_add_match_view),  name="admin_quick_match"),
    path("admin/players/quick/",  admin.site.admin_view(quick_add_players_view), name="admin_quick_players"),

    path("admin/events/quick/",   admin.site.admin_view(quick_events),          name="admin_quick_events"),
    path("admin/events/api/",     admin.site.admin_view(quick_events_api),      name="admin_quick_events_api"),

    path("admin/lineups/quick/",  admin.site.admin_view(quick_lineups),         name="admin_quick_lineups"),
    path("admin/lineups/api/",    admin.site.admin_view(quick_lineups_api),     name="admin_quick_lineups_api"),

    path("admin/clubs/quick/",                admin.site.admin_view(quick_clubs),  name="quick_clubs"),
    path("admin/clubs/quick/<int:club_id>/",  admin.site.admin_view(quick_roster), name="quick_roster"),
    path("admin/clubs/quick/api/",            admin.site.admin_view(quick_clubs_api), name="quick_clubs_api"),

    # JSON utilitaires pour l’admin (utilisé par la page Compos rapides)
    path(
        "admin/clubs/<int:club_id>/players/",
        admin.site.admin_view(admin_players_by_club),
        name="admin_players_by_club",
    ),

    # Alias (si tu as une entrée de menu personnalisée)
    path("admin/livefootgn/", admin.site.admin_view(quick_add_match_view), name="admin_livefootgn"),

    # Interface d’admin classique
    path("admin/", admin.site.urls),

    # ===== Auth & APIs publiques =====
    path("api/auth/token/",         TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(),    name="token_refresh"),

    # Modules d'API
    path("api/stats/", include("stats.urls")),
    path("api/", include("clubs.urls")),
    path("api/", include("players.urls")),
    path("api/", include("matches.urls")),
    path("api/", include("news.urls")),
    path("api/", include("recruitment.urls")),
    path("api/", include("users.urls")),
]

# Fichiers média
if settings.DEBUG:
    # Dev: via static()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Prod/Staging (Render): exposer /media/ via Django
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
            name="media",
        ),
    ]
