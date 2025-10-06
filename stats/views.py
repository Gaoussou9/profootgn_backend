# stats/views.py
from collections import defaultdict

from django.db.models import Q, Count
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from clubs.models import Club
from matches.models import Match, Goal, Card  # Card utilisé pour la doc / cohérence imports
from players.models import Player


# Statuts pris en compte
FINISHED_STATUSES = {"FT", "FINISHED"}
LIVE_STATUSES = {"LIVE", "HT", "PAUSED"}  # ajoute "SUSPENDED" si tu veux l’inclure


def _abs_url(request, url_or_field):
    """Retourne une URL absolue pour un FileField/CharField/str, sinon None."""
    if not url_or_field:
        return None
    try:
        u = url_or_field.url  # FileField
    except Exception:
        u = str(url_or_field)
    if not u:
        return None
    if u.startswith("http"):
        return u
    return request.build_absolute_uri(u) if request else u


def _club_logo_url(club, request):
    for attr in ("logo", "logo_url", "image"):
        if hasattr(club, attr):
            u = _abs_url(request, getattr(club, attr))
            if u:
                return u
    return None


class StandingsView(APIView):
    """
    GET /api/stats/standings/?include_live=1
    -> tableau trié (points, diff, BM) avec logo & méta club
    """
    permission_classes = [AllowAny]

    def get(self, request):
        include_live = str(request.query_params.get("include_live", "")).lower() in {"1", "true", "yes", "y"}

        # base: une ligne par club
        clubs = Club.objects.all()
        table = {
            c.id: {
                "club_id": c.id,
                "club_name": getattr(c, "name", str(c)),
                "club_logo": _club_logo_url(c, request),
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_diff": 0,
                "points": 0,
            }
            for c in clubs
        }

        def apply_match(m):
            if m.home_score is None or m.away_score is None:
                return
            hs, as_ = int(m.home_score), int(m.away_score)
            h_id, a_id = m.home_club_id, m.away_club_id
            th, ta = table.get(h_id), table.get(a_id)
            if not th or not ta:
                return

            th["played"] += 1
            ta["played"] += 1
            th["goals_for"] += hs
            th["goals_against"] += as_
            ta["goals_for"] += as_
            ta["goals_against"] += hs

            if hs > as_:
                th["wins"] += 1
                ta["losses"] += 1
                th["points"] += 3
            elif hs < as_:
                ta["wins"] += 1
                th["losses"] += 1
                ta["points"] += 3
            else:
                th["draws"] += 1
                ta["draws"] += 1
                th["points"] += 1
                ta["points"] += 1

        # terminés
        for m in (
            Match.objects
            .only("id", "home_club_id", "away_club_id", "home_score", "away_score", "status")
            .filter(status__in=FINISHED_STATUSES)
        ):
            apply_match(m)

        # live (provisoire)
        if include_live:
            live_qs = (
                Match.objects
                .only("id", "home_club_id", "away_club_id", "home_score", "away_score", "status")
                .filter(status__in=LIVE_STATUSES)
                .exclude(home_score__isnull=True)
                .exclude(away_score__isnull=True)
            )
            for m in live_qs:
                apply_match(m)

        # diff + tri
        rows = []
        for r in table.values():
            r["goal_diff"] = r["goals_for"] - r["goals_against"]
            rows.append(r)

        rows.sort(key=lambda r: (-r["points"], -r["goal_diff"], -r["goals_for"], r["club_name"]))
        for i, r in enumerate(rows, start=1):
            r["position"] = i
        return Response(rows)


class TopScorersView(APIView):
    """
    GET /api/stats/topscorers/?include_live=1&limit=50
    -> [{ player: {id, first_name, last_name, number, photo}, club_name, goals }]
    """
    permission_classes = [AllowAny]

    def get(self, request):
        include_live = str(request.query_params.get("include_live", "")).lower() in {"1", "true", "yes", "y"}
        try:
            limit = int(request.query_params.get("limit", 50))
        except Exception:
            limit = 50

        status_set = set(FINISHED_STATUSES)
        if include_live:
            status_set |= set(LIVE_STATUSES)

        # Compte les buts par joueur (ignore null)
        agg = (
            Goal.objects
            .filter(match__status__in=status_set, player__isnull=False)
            .values("player_id")
            .annotate(goals=Count("id"))
            .order_by("-goals", "player_id")
        )

        # Récup infos joueurs associées
        player_ids = [a["player_id"] for a in agg[:limit]]
        players = (
            Player.objects
            .select_related("club")
            .only("id", "first_name", "last_name", "number", "photo", "club__name")
            .in_bulk(player_ids)
        )

        rows = []
        for a in agg[:limit]:
            p = players.get(a["player_id"])
            if not p:
                continue
            rows.append({
                "player": {
                    "id": p.id,
                    "first_name": p.first_name or "",
                    "last_name": p.last_name or "",
                    "number": p.number,
                    "photo": _abs_url(request, p.photo),
                },
                "club_name": getattr(p.club, "name", "") if getattr(p, "club", None) else "",
                "goals": a["goals"],
            })

        return Response(rows)


class PlayerTotalsView(APIView):
    """
    GET /api/stats/player-totals/?club=<id>&include_live=1
    → [{id, full_name, goals, assists, yellows, reds}]
    Calcule à partir de Goal (buts/assists) et Card (Y/R).
    """
    permission_classes = [AllowAny]

    def get(self, request):
        club_id = request.query_params.get("club")
        include_live = str(request.query_params.get("include_live", "")).lower() in {"1", "true", "yes", "y"}

        status_set = set(FINISHED_STATUSES)
        if include_live:
            status_set |= set(LIVE_STATUSES)
        status_list = list(status_set)

        # Base: joueurs du club si fourni, sinon tous
        players_qs = Player.objects.all()
        if club_id:
            players_qs = players_qs.filter(club_id=club_id)

        # Filtres dynamiques
        gq = Q(goal__match__status__in=status_list)
        aq = Q(assists__match__status__in=status_list)      # reverse FK Goal.assist_player (related_name='assists')
        yq = Q(card__match__status__in=status_list, card__type="Y")
        rq = Q(card__match__status__in=status_list, card__type="R")

        if club_id:
            gq &= Q(goal__club_id=club_id)
            aq &= Q(assists__club_id=club_id)
            yq &= Q(card__club_id=club_id)
            rq &= Q(card__club_id=club_id)

        # ⚠️ IMPORTANT : utiliser des alias différents des noms de champs existants
        qs = (
            players_qs
            .annotate(
                goals_total=Count("goal",       filter=gq),
                assists_total=Count("assists",  filter=aq),
                yellows_total=Count("card",     filter=yq),
                reds_total=Count("card",        filter=rq),
            )
            .values(
                "id", "first_name", "last_name",
                "goals_total", "assists_total", "yellows_total", "reds_total"
            )
            .order_by("last_name", "first_name")
        )

        rows = []
        for r in qs:
            full = f'{(r["first_name"] or "").strip()} {(r["last_name"] or "").strip()}'.strip() or "—"
            rows.append({
                "id": r["id"],
                "full_name": full,
                "goals":   int(r["goals_total"]   or 0),
                "assists": int(r["assists_total"] or 0),
                "yellows": int(r["yellows_total"] or 0),
                "reds":    int(r["reds_total"]    or 0),
            })
        return Response(rows)
