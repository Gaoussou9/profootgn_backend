from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from rest_framework import viewsets, filters, permissions, status, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAdminUser

from django_filters.rest_framework import DjangoFilterBackend

from .models import Match, Goal, Card, Round, Lineup, TeamInfoPerMatch
from .serializers import (
    MatchSerializer,
    GoalSerializer,
    CardSerializer,
    RoundSerializer,
    LineupSerializer,
    TeamInfoPerMatchSerializer as TeamInfoSerializer,
    LineupWriteSerializer,
)

from players.models import Player
from clubs.models import Club
from collections import defaultdict


GOALS_REL_NAME = Goal._meta.get_field("match").remote_field.get_accessor_name()
CARDS_REL_NAME = Card._meta.get_field("match").remote_field.get_accessor_name()


class ReadOnlyOrAdmin(permissions.IsAdminUser):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return super().has_permission(request, view)


# ----------------------------------------------------
# Horloge live envoyée au front
# ----------------------------------------------------
def _clock_payload_for_match(m: Match):
    """
    On renvoie au front assez d'info pour animer la minute localement
    entre deux rafraîchissements API.

    Convention:
    - live_phase_start: ISO timestamp (timezone-aware) du début de la période en cours
        * 1ère MT -> kickoff_1
        * 2ème MT -> kickoff_2
    - live_phase_offset: minutes déjà jouées au début de cette période
        * 1ère MT -> 0
        * 2ème MT -> 45

    Le front peut ensuite faire :
        nowDiffMin = floor((Date.now - live_phase_start)/60s)
        minute = live_phase_offset + nowDiffMin
        puis afficher "45’+" etc.

    Pour les statuts statiques (HT, FT...), on renvoie None/None.
    Ça dit au front: pas d'animation.
    """
    st = (getattr(m, "status", "") or "").upper()

    if st == "LIVE":
        # 2e mi-temps ?
        if getattr(m, "kickoff_2", None):
            return {
                "live_phase_start": m.kickoff_2.isoformat(),
                "live_phase_offset": 45,
            }
        # 1ère mi-temps ?
        if getattr(m, "kickoff_1", None):
            return {
                "live_phase_start": m.kickoff_1.isoformat(),
                "live_phase_offset": 0,
            }
        # LIVE mais pas de kickoff connu -> rien
        return {
            "live_phase_start": None,
            "live_phase_offset": None,
        }

    # HT / PAUSED / FT / FINISHED / SCHEDULED / etc => pas d'horloge qui bouge
    return {
        "live_phase_start": None,
        "live_phase_offset": None,
    }


def _augment_matches_with_clock(matches, request):
    """
    matches: iterable d'instances Match
    -> retourne une liste de dicts (serializer.data) avec en plus :
         - live_phase_start
         - live_phase_offset

    IMPORTANT:
    On passe "request" dans le serializer context pour que
    MatchSerializer / GoalSerializer / CardSerializer / LineupSerializer
    puissent construire les URLs ABSOLUES (logos, photos).
    """
    out = []
    for m in matches:
        base = MatchSerializer(m, context={"request": request}).data
        clock_info = _clock_payload_for_match(m)
        base["live_phase_start"] = clock_info["live_phase_start"]
        base["live_phase_offset"] = clock_info["live_phase_offset"]
        out.append(base)
    return out


class MatchViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrAdmin]
    serializer_class = MatchSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "round_id": ["exact", "in"],
        "round__name": ["iexact"],
        "round__number": ["exact", "in"],
        "status": ["exact", "in"],
    }
    search_fields = ["home_club__name", "away_club__name", "venue"]
    ordering_fields = ["datetime", "minute", "id"]
    ordering = ["-datetime", "-id"]

    def get_queryset(self):
        qs_goals = Goal.objects.select_related("player", "club").order_by("minute", "id")
        qs_cards = Card.objects.select_related("player", "club").order_by("minute", "id")
        qs_lineups = (
            Lineup.objects.select_related("player", "club")
            .order_by("club_id", "-is_starting", "number", "id")
        )

        qs = (
            Match.objects.select_related("home_club", "away_club", "round")
            .prefetch_related(
                Prefetch(GOALS_REL_NAME, queryset=qs_goals),
                Prefetch(CARDS_REL_NAME, queryset=qs_cards),
                Prefetch("lineups", queryset=qs_lineups),
            )
        )

        qp = self.request.query_params

        rn = qp.get("round_number")
        if rn:
            nums = [int(x) for x in str(rn).split(",") if x.strip().isdigit()]
            if nums:
                qs = qs.filter(round__number__in=nums)

        rid = qp.get("round_id")
        if rid:
            ids = [int(x) for x in str(rid).split(",") if x.strip().isdigit()]
            if ids:
                qs = qs.filter(round_id__in=ids)

        rname = qp.get("round")
        if rname:
            qs = qs.filter(round__name__iexact=str(rname).strip())

        status_q = qp.get("status")
        date_from = qp.get("date_from")
        date_to = qp.get("date_to")

        if status_q:
            s = status_q.upper()
            if s == "FINISHED":
                qs = qs.filter(status__in=["FT", "FINISHED"])
            elif s == "LIVE":
                qs = qs.filter(status__in=["LIVE", "HT", "PAUSED"])
            else:
                qs = qs.filter(status=s)

        if date_from:
            d = parse_date(date_from)
            if d:
                qs = qs.filter(datetime__date__gte=d)
        if date_to:
            d = parse_date(date_to)
            if d:
                qs = qs.filter(datetime__date__lte=d)

        return qs

    # list / retrieve / actions custom => on ajoute live_phase_* et on garde request
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        data = _augment_matches_with_clock(qs, request)
        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        m = self.get_object()
        data = _augment_matches_with_clock([m], request)[0]
        return Response(data)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        limit = int(
            request.query_params.get("page_size")
            or request.query_params.get("limit")
            or 10
        )
        qs = (
            self.get_queryset()
            .filter(status__in=["FT", "FINISHED"])
            .order_by("-datetime", "-id")[:limit]
        )
        data = _augment_matches_with_clock(qs, request)
        return Response(data)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        limit = int(
            request.query_params.get("page_size")
            or request.query_params.get("limit")
            or 10
        )
        now = timezone.now()
        qs = (
            self.get_queryset()
            .filter(status="SCHEDULED", datetime__gte=now)
            .order_by("datetime", "id")[:limit]
        )
        data = _augment_matches_with_clock(qs, request)
        return Response(data)

    @action(detail=False, methods=["get"])
    def live(self, request):
        qs = (
            self.get_queryset()
            .filter(status__in=["LIVE", "HT", "PAUSED"])
            .order_by("-datetime", "-id")
        )
        data = _augment_matches_with_clock(qs, request)
        return Response(data)

    @action(
        detail=True,
        methods=["get"],
        url_path="lineups",
        permission_classes=[permissions.AllowAny],
    )
    def action_lineups(self, request, pk=None):
        qs = (
            Lineup.objects.filter(match_id=pk)
            .select_related("club", "player")
            .order_by("club_id", "-is_starting", "number", "id")
        )
        data = LineupSerializer(qs, many=True, context={"request": request}).data
        return Response(data)

    @action(
        detail=True,
        methods=["get", "put"],
        url_path="team-info",
        permission_classes=[ReadOnlyOrAdmin],
    )
    def action_team_info(self, request, pk=None):
        m = get_object_or_404(Match, pk=pk)

        if request.method == "GET":
            infos = TeamInfoPerMatch.objects.filter(match=m).select_related("club")
            home = away = None
            for ti in infos:
                if ti.club_id == m.home_club_id:
                    home = TeamInfoSerializer(ti).data
                elif ti.club_id == m.away_club_id:
                    away = TeamInfoSerializer(ti).data
            return Response({"home": home, "away": away})

        payload = request.data or {}
        out = {"home": None, "away": None}
        for side, club_id in (("home", m.home_club_id), ("away", m.away_club_id)):
            block = payload.get(side) or {}
            if not isinstance(block, dict):
                continue
            ti, _ = TeamInfoPerMatch.objects.get_or_create(match=m, club_id=club_id)
            ti.formation = (block.get("formation") or "").strip()
            ti.coach_name = (block.get("coach_name") or "").strip()
            ti.save()
            out[side] = TeamInfoSerializer(ti).data
        return Response(out, status=status.HTTP_200_OK)


class GoalViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [ReadOnlyOrAdmin]

    queryset = Goal.objects.select_related("match", "player", "club")
    serializer_class = GoalSerializer

    @action(
        detail=False,
        methods=["get"],
        url_path="by-match",
        permission_classes=[permissions.AllowAny],
    )
    def by_match(self, request):
        mid = request.query_params.get("match")
        if not mid:
            return Response({"detail": "Paramètre 'match' requis."}, status=400)
        qs = (
            Goal.objects.filter(match_id=mid)
            .select_related("player", "club")
            .order_by("minute", "id")
        )
        return Response(
            GoalSerializer(qs, many=True, context={"request": request}).data
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk",
        permission_classes=[IsAdminUser],
    )
    def bulk(self, request):
        match_id = request.data.get("match")
        goals_in = request.data.get("goals", [])
        replace = bool(request.data.get("replace"))

        if not match_id or not isinstance(goals_in, list):
            return Response(
                {"ok": False, "detail": "Paramètres invalides."}, status=400
            )

        match = get_object_or_404(Match, pk=match_id)
        allowed_clubs = {match.home_club_id, match.away_club_id}

        with transaction.atomic():
            if replace:
                Goal.objects.filter(match=match).delete()

            to_create = []
            for g in goals_in:
                club_id = g.get("club")
                try:
                    club_id = int(club_id)
                except (TypeError, ValueError):
                    continue
                if club_id not in allowed_clubs:
                    continue
                club = get_object_or_404(Club, pk=club_id)

                minute = g.get("minute") or 0
                try:
                    minute = int(minute)
                except Exception:
                    minute = 0

                player = None
                player_id = g.get("player")
                player_name = (g.get("player_name") or "").strip()
                if player_id:
                    player = get_object_or_404(Player, pk=player_id)
                elif player_name:
                    if hasattr(Player, "club"):
                        player = Player.objects.filter(
                            name__iexact=player_name, club=club
                        ).first()
                        if not player:
                            player, _ = Player.objects.get_or_create(
                                name=player_name, defaults={"club": club}
                            )
                        elif getattr(player, "club_id", None) is None:
                            player.club = club
                            player.save(update_fields=["club"])
                    else:
                        player, _ = Player.objects.get_or_create(name=player_name)

                assist_player = None
                assist_name = (
                    g.get("assist_name") or g.get("assist_player_name") or ""
                ).strip()
                assist_id = g.get("assist_player")
                if assist_id:
                    assist_player = get_object_or_404(Player, pk=assist_id)
                elif assist_name:
                    if hasattr(Player, "club"):
                        assist_player = Player.objects.filter(
                            name__iexact=assist_name, club=club
                        ).first()
                        if not assist_player:
                            assist_player, _ = Player.objects.get_or_create(
                                name=assist_name, defaults={"club": club}
                            )
                        elif getattr(assist_player, "club_id", None) is None:
                            assist_player.club = club
                            assist_player.save(update_fields=["club"])
                    else:
                        assist_player = None

                to_create.append(
                    Goal(
                        match=match,
                        club=club,
                        player=player,
                        minute=minute,
                        assist_player=assist_player if assist_player else None,
                        assist_name=("" if assist_player else assist_name),
                    )
                )

            if to_create:
                Goal.objects.bulk_create(to_create)

        qs = (
            Goal.objects.filter(match=match)
            .select_related("player", "club")
            .order_by("minute", "id")
        )
        data = GoalSerializer(
            qs, many=True, context={"request": request}
        ).data
        return Response({"ok": True, "created": data})


class CardViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrAdmin]
    queryset = Card.objects.select_related("match", "player", "club")
    serializer_class = CardSerializer


class RoundViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrAdmin]
    queryset = Round.objects.all().order_by("id")
    serializer_class = RoundSerializer


class LineupViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [ReadOnlyOrAdmin]
    queryset = Lineup.objects.select_related("match", "club", "player")
    serializer_class = LineupSerializer

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LineupWriteSerializer
        return LineupSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {"match": ["exact"], "club": ["exact"], "is_starting": ["exact"]}
    search_fields = [
        "player_name",
        "player__name",
        "player__first_name",
        "player__last_name",
    ]
    ordering_fields = ["match", "club", "is_starting", "number", "id"]
    ordering = ["match", "club", "-is_starting", "number", "id"]


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def match_lineups(request, pk: int):
    qs = (
        Lineup.objects.filter(match_id=pk)
        .select_related("club", "player")
        .order_by("club_id", "-is_starting", "number", "id")
    )
    data = LineupSerializer(qs, many=True, context={"request": request}).data
    return Response(data)


@api_view(["GET", "PUT"])
@permission_classes([ReadOnlyOrAdmin])
def match_team_info(request, pk: int):
    m = get_object_or_404(Match, pk=pk)

    if request.method == "GET":
        infos = TeamInfoPerMatch.objects.filter(match=m).select_related("club")
        home = away = None
        for ti in infos:
            if ti.club_id == m.home_club_id:
                home = TeamInfoSerializer(ti).data
            elif ti.club_id == m.away_club_id:
                away = TeamInfoSerializer(ti).data
        return Response({"home": home, "away": away})

    payload = request.data or {}
    out = {"home": None, "away": None}
    for side, club_id in (("home", m.home_club_id), ("away", m.away_club_id)):
        block = payload.get(side) or {}
        if not isinstance(block, dict):
            continue
        ti, _ = TeamInfoPerMatch.objects.get_or_create(match=m, club_id=club_id)
        ti.formation = (block.get("formation") or "").strip()
        ti.coach_name = (block.get("coach_name") or "").strip()
        ti.save()
        out[side] = TeamInfoSerializer(ti).data
    return Response(out, status=status.HTTP_200_OK)


def _post(request, key, default=None):
    return request.POST.get(key, default)


def _to_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _parse_dt(raw):
    if not raw:
        return timezone.now()
    dt = parse_datetime(raw)
    if not dt:
        return timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _resolve_club(val, allow_create=False):
    if not val:
        return None
    s = str(val).strip()
    if s.isdigit():
        return Club.objects.filter(pk=int(s)).first()
    qs = Club.objects.filter(name__iexact=s)
    if qs.exists():
        return qs.first()
    return Club.objects.create(name=s) if allow_create else None


def _resolve_round(val):
    if not val:
        return None
    s = str(val).strip()
    if s.isdigit():
        return Round.objects.filter(pk=int(s)).first()
    return Round.objects.filter(name__iexact=s).first()


@require_POST
def ajouter_match(request):
    home_val = _post(request, "home_id") or _post(request, "team1") or _post(request, "home")
    away_val = _post(request, "away_id") or _post(request, "team2") or _post(request, "away")

    home = _resolve_club(home_val, allow_create=False)
    away = _resolve_club(away_val, allow_create=False)
    if not home or not away:
        return HttpResponseBadRequest("Clubs invalides")
    if home == away:
        return HttpResponseBadRequest("Les deux équipes ne peuvent pas être identiques.")

    rnd = _resolve_round(_post(request, "journee") or _post(request, "round_id"))
    dt = _parse_dt(_post(request, "datetime") or _post(request, "kickoff_at"))

    m = Match.objects.create(
        round=rnd,
        datetime=dt,
        home_club=home,
        away_club=away,
        home_score=_to_int(_post(request, "score1") or _post(request, "home_score"), 0),
        away_score=_to_int(_post(request, "score2") or _post(request, "away_score"), 0),
        minute=_to_int(_post(request, "minute"), 0),
        status=(_post(request, "status") or "SCHEDULED").upper(),
        venue=_post(request, "venue", "") or "",
        **({"buteur": (_post(request, "buteur") or "").strip()} if hasattr(Match, "buteur") else {}),
    )
    return JsonResponse({"ok": True, "id": m.id})


@require_POST
def modifier_match(request):
    mid = _post(request, "id")
    if not mid:
        return HttpResponseBadRequest("id manquant")

    m = get_object_or_404(Match, pk=mid)

    # Clubs
    if "home_id" in request.POST or "team1" in request.POST or "home" in request.POST:
        c = _resolve_club(_post(request, "home_id") or _post(request, "team1") or _post(request, "home"))
        if c:
            m.home_club = c
    if "away_id" in request.POST or "team2" in request.POST or "away" in request.POST:
        c = _resolve_club(_post(request, "away_id") or _post(request, "team2") or _post(request, "away"))
        if c:
            m.away_club = c

    # Scores / minute (minute reste un fallback legacy)
    if "home_score" in request.POST or "score1" in request.POST:
        m.home_score = _to_int(_post(request, "home_score") or _post(request, "score1"), m.home_score)
    if "away_score" in request.POST or "score2" in request.POST:
        m.away_score = _to_int(_post(request, "away_score") or _post(request, "score2"), m.away_score)
    if "minute" in request.POST:
        m.minute = _to_int(_post(request, "minute"), m.minute)

    # Round
    if "journee" in request.POST or "round_id" in request.POST:
        r = _resolve_round(_post(request, "journee") or _post(request, "round_id"))
        if r:
            m.round = r

    # Status (et gestion des kicks off)
    if "status" in request.POST:
        new_status = (_post(request, "status") or m.status).upper()

        if new_status == "LIVE":
            # Si on passe LIVE :
            # 1ère MT : kickoff_1 manquant -> le définir maintenant.
            if m.kickoff_1 is None:
                m.kickoff_1 = timezone.now()

            # Reprise 2ème MT : si on venait de HT/PAUSED et kickoff_2 pas encore défini -> le définir maintenant.
            if m.status in ["HT", "PAUSED"] and m.kickoff_2 is None:
                m.kickoff_2 = timezone.now()

        m.status = new_status

    # Lieu / datetime / buteur
    if "venue" in request.POST:
        m.venue = _post(request, "venue") or ""
    if "datetime" in request.POST or "kickoff_at" in request.POST:
        m.datetime = _parse_dt(_post(request, "datetime") or _post(request, "kickoff_at"))
    if hasattr(Match, "buteur") and "buteur" in request.POST:
        m.buteur = _post(request, "buteur") or ""

    m.save()
    return JsonResponse({"ok": True})


@require_POST
def supprimer_match(request):
    mid = _post(request, "id")
    if not mid:
        return HttpResponseBadRequest("id manquant")
    get_object_or_404(Match, pk=mid).delete()
    return JsonResponse({"ok": True})


@require_POST
def suspendre_match(request):
    mid = _post(request, "id")
    if not mid:
        return HttpResponseBadRequest("id manquant")
    m = get_object_or_404(Match, pk=mid)
    m.status = "SUSPENDED"
    m.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": m.status})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def standings_view(request):
    include_live = str(request.query_params.get("include_live", "1")).lower() in {
        "1", "true", "yes", "on"
    }
    debug_flag = str(request.query_params.get("debug", "0")).lower() in {
        "1", "true", "yes", "on"
    }

    finished = ("FT", "FINISHED")
    liveish = ("LIVE", "HT", "PAUSED")

    def _abs_logo(club):
        """
        URL absolue du logo club (ou None).
        """
        if not club or not getattr(club, "logo", None):
            return None
        try:
            raw = club.logo.url
        except Exception:
            raw = str(getattr(club, "logo", "")).strip()
            if not raw:
                return None
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        return request.build_absolute_uri(raw) if request else raw

    # tableau init
    rows = {}
    for c in Club.objects.all().order_by("name"):
        rows[c.id] = {
            "club_id": c.id,
            "club_name": c.name,
            "club_logo": _abs_logo(c),
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_diff": 0,
            "points": 0,
        }

    statuses = finished + (liveish if include_live else ())
    qs = (
        Match.objects.filter(status__in=statuses)
        .select_related("home_club", "away_club")
        .order_by("datetime", "id")
    )

    # fallback si pas de matches terminés (ex: début de saison) ET include_live=0
    if not qs.exists() and not include_live:
        statuses = finished + liveish
        qs = (
            Match.objects.filter(status__in=statuses)
            .select_related("home_club", "away_club")
            .order_by("datetime", "id")
        )

    counted = 0
    for m in qs:
        if not m.home_club_id or not m.away_club_id:
            continue
        h, a = m.home_club_id, m.away_club_id
        hs, as_ = int(m.home_score or 0), int(m.away_score or 0)

        rows[h]["played"] += 1
        rows[a]["played"] += 1

        rows[h]["goals_for"] += hs
        rows[h]["goals_against"] += as_
        rows[a]["goals_for"] += as_
        rows[a]["goals_against"] += hs

        if hs > as_:
            rows[h]["wins"] += 1
            rows[a]["losses"] += 1
            rows[h]["points"] += 3
        elif hs < as_:
            rows[a]["wins"] += 1
            rows[h]["losses"] += 1
            rows[a]["points"] += 3
        else:
            rows[h]["draws"] += 1
            rows[a]["draws"] += 1
            rows[h]["points"] += 1
            rows[a]["points"] += 1

        counted += 1

    out = []
    for r in rows.values():
        r["goal_diff"] = r["goals_for"] - r["goals_against"]
        out.append(r)

    out.sort(
        key=lambda x: (
            -x["points"],
            -x["goal_diff"],
            -x["goals_for"],
            x["club_name"].lower(),
        )
    )

    if debug_flag:
        return Response(
            {
                "debug": {
                    "statuses_used": list(statuses),
                    "matches_counted": counted,
                    "include_live": include_live,
                },
                "table": out,
            }
        )
    return Response(out)


# ---------- utilitaires communs ----------
def _abs_media(request, file_or_url):
    """
    Renvoyer une URL absolue pour une image (photo joueur, logo club...).
    """
    if not file_or_url:
        return None
    try:
        url = file_or_url.url
    except Exception:
        url = str(file_or_url).strip()
        if not url:
            return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return request.build_absolute_uri(url) if request else url


def _player_fullname(p):
    if getattr(p, "name", None):
        return (p.name or "").strip()
    return f"{getattr(p,'first_name','')} {getattr(p,'last_name','')}".strip()


def _is_own_goal(goal):
    t = (getattr(goal, "type", "") or getattr(goal, "kind", "") or "").upper()
    return bool(getattr(goal, "own_goal", False)) or t in {
        "OG",
        "CSC",
        "OWN_GOAL",
        "OWNGOAL",
    }


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def assists_leaders(request):
    include_live = str(request.query_params.get("include_live", "1")).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        limit = int(request.query_params.get("limit") or 100)
    except Exception:
        limit = 100

    club_filter = request.query_params.get("club")
    club_id = int(club_filter) if (club_filter and str(club_filter).isdigit()) else None

    finished = ("FT", "FINISHED")
    liveish = ("LIVE", "HT", "PAUSED")
    statuses = finished + (liveish if include_live else ())

    matches_qs = Match.objects.filter(status__in=statuses).only("id")
    goals_qs = (
        Goal.objects.filter(match__in=matches_qs)
        .select_related("assist_player", "assist_player__club", "player", "club")
        .only(
            "id",
            "assist_player_id",
            "assist_name",
            "player_id",
            "player_name",
            "club_id",
        )
        .order_by("id")
    )
    if club_id:
        goals_qs = goals_qs.filter(club_id=club_id)

    club_ids = set(goals_qs.values_list("club_id", flat=True))
    name_index = {}
    if club_ids:
        ps = (
            Player.objects.filter(club_id__in=club_ids)
            .select_related("club")
            .only(
                "id",
                "name",
                "first_name",
                "last_name",
                "club_id",
                "photo",
            )
        )
        for p in ps:
            nm = _player_fullname(p)
            if nm:
                name_index[(p.club_id, nm.lower())] = p

    counts = defaultdict(int)
    meta = {}

    for g in goals_qs:
        scorer = g.player
        if not scorer:
            pname = (getattr(g, "player_name", "") or "").strip().lower()
            scorer = name_index.get((g.club_id, pname))
        scorer_id = getattr(scorer, "id", None)

        p = g.assist_player
        if not p:
            nm = (g.assist_name or "").strip().lower()
            if nm:
                p = name_index.get((g.club_id, nm))
        if not p:
            continue

        # pas d'assist créditée au buteur lui-même
        if scorer_id and getattr(p, "id", None) == scorer_id:
            continue

        counts[p.id] += 1
        if p.id not in meta:
            club = getattr(p, "club", None)
            meta[p.id] = {
                "player_id": p.id,
                "player_name": _player_fullname(p) or f"Joueur #{p.id}",
                "player_photo": _abs_media(request, getattr(p, "photo", None)),
                "club_id": getattr(club, "id", None),
                "club_name": getattr(club, "name", None),
                "club_logo": _abs_media(
                    request, getattr(club, "logo", None) if club else None
                ),
            }

    rows = [{**meta[pid], "assists": int(n)} for pid, n in counts.items()]
    rows.sort(key=lambda x: (-x["assists"], (x.get("player_name") or "").lower()))
    if limit > 0:
        rows = rows[:limit]
    return Response(rows)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def search_players(request):
    q = (request.query_params.get("q") or "").strip()
    club_id = request.query_params.get("club")
    try:
        limit = int(request.query_params.get("limit") or 20)
    except Exception:
        limit = 20

    qs = Player.objects.all()

    if club_id and str(club_id).isdigit() and hasattr(Player, "club"):
        qs = qs.filter(club_id=int(club_id))

    if q:
        filt = Q()
        if hasattr(Player, "name"):
            filt |= Q(name__icontains=q)
        if hasattr(Player, "first_name"):
            filt |= Q(first_name__icontains=q)
        if hasattr(Player, "last_name"):
            filt |= Q(last_name__icontains=q)
        if filt:
            qs = qs.filter(filt)

    qs = qs.select_related("club")[:limit]

    out = []
    for p in qs:
        club = getattr(p, "club", None)
        name = (
            getattr(p, "name", None)
            or f"{getattr(p,'first_name','')} {getattr(p,'last_name','')}".strip()
            or f"Joueur #{p.pk}"
        )
        out.append(
            {
                "id": p.id,
                "name": name,
                "club_id": getattr(club, "id", None),
                "club_name": getattr(club, "name", None),
            }
        )
    return Response(out)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def club_players_stats(request, club_id: int):
    club = get_object_or_404(Club, pk=club_id)

    m_q = Q(home_club=club) | Q(away_club=club)
    match_ids = list(Match.objects.filter(m_q).values_list("id", flat=True))

    players_rel = getattr(club, "players", None)
    if players_rel and hasattr(players_rel, "all"):
        players = list(players_rel.all())
    else:
        players = list(Player.objects.filter(club=club))
    id_to_player = {p.id: p for p in players}
    name_to_id = {}
    for p in players:
        full = _player_fullname(p)
        if full:
            name_to_id[full.lower()] = p.id

    agg = defaultdict(lambda: {"goals": 0, "assists": 0, "yc": 0, "rc": 0})

    goals = (
        Goal.objects.filter(match_id__in=match_ids, club=club)
        .select_related("player", "assist_player")
        .order_by("minute", "id")
    )
    for g in goals:
        scorer_pid = None
        if not _is_own_goal(g):
            if g.player_id:
                scorer_pid = g.player_id
            else:
                pname = (getattr(g, "player_name", "") or "").strip().lower()
                if pname and pname in name_to_id:
                    scorer_pid = name_to_id[pname]
            if scorer_pid in id_to_player:
                agg[scorer_pid]["goals"] += 1

        aid = None
        raw_assist = (getattr(g, "assist_name", "") or "").strip()
        if getattr(g, "assist_player_id", None):
            aid = g.assist_player_id
        elif raw_assist:
            aname = raw_assist.lower()
            if aname in name_to_id:
                aid = name_to_id[aname]
        if aid and aid != scorer_pid and aid in id_to_player:
            agg[aid]["assists"] += 1

    cards = (
        Card.objects.filter(match_id__in=match_ids, club=club)
        .select_related("player")
        .order_by("minute", "id")
    )
    for c in cards:
        pid = None
        if c.player_id:
            pid = c.player_id
        else:
            cname = (getattr(c, "player_name", "") or "").strip().lower()
            if cname and cname in name_to_id:
                pid = name_to_id[cname]
        if pid not in id_to_player:
            continue
        color = (getattr(c, "color", "") or getattr(c, "type", "") or "").upper()
        if color.startswith("R"):
            agg[pid]["rc"] += 1
        else:
            agg[pid]["yc"] += 1

    rows = []
    for p in players:
        s = agg.get(p.id, {})
        rows.append(
            {
                "id": p.id,
                "name": _player_fullname(p) or f"Joueur #{p.id}",
                "number": getattr(p, "number", None),
                "position": getattr(p, "position", None),
                "photo": _abs_media(request, getattr(p, "photo", None)),
                "goals": int(s.get("goals", 0) or 0),
                "assists": int(s.get("assists", 0) or 0),
                "yc": int(s.get("yc", 0) or 0),
                "rc": int(s.get("rc", 0) or 0),
            }
        )

    rows.sort(
        key=lambda r: (-r["goals"], -r["assists"], (r["name"] or "").lower())
    )
    return Response(
        {
            "club": {
                "id": club.id,
                "name": club.name,
                "logo": _abs_media(request, getattr(club, "logo", None)),
            },
            "players": rows,
        }
    )
