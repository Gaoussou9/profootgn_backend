from rest_framework import serializers
from django.utils import timezone

from .models import (
    Match, Goal, Card, Round,
    Lineup, TeamInfoPerMatch,
)

# Managers inverses dynamiques (goals/cards)
GOALS_REL_NAME = Goal._meta.get_field("match").remote_field.get_accessor_name()
CARDS_REL_NAME = Card._meta.get_field("match").remote_field.get_accessor_name()


# ---------- Helpers ----------
def _abs_any(request, value):
    """
    Retourne une URL absolue quelle que soit la nature du champ :
    - File/ImageField (FieldFile) -> .url
    - str (URLField) -> renvoyé tel quel si absolu, sinon absolutisé
    Renvoie None si pas exploitable.
    """
    if not value:
        return None

    # Essayer d'obtenir .url (FieldFile)
    try:
        url = value.url
    except Exception:
        url = None

    # Sinon traiter 'value' comme string
    if url is None:
        url = str(value).strip()
        if not url:
            return None

    # Absolutiser si besoin
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return request.build_absolute_uri(url) if request else url


def _short_name(full: str | None) -> str | None:
    if not full:
        return None
    name = str(full).strip().replace("  ", " ")
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    particles = {
        "de","du","des","da","dos","del","della","van","von","der","den",
        "di","le","la","el","al","bin","ibn"
    }
    first = parts[0]
    i = len(parts) - 1
    last = parts[i]
    i -= 1
    while i > 0 and parts[i].lower() in particles:
        last = parts[i] + " " + last
        i -= 1
    return f"{first[0].upper()}. {last}"


# ---------- ROUND ----------
class RoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Round
        fields = "__all__"


# ---------- GOALS ----------
class GoalSerializer(serializers.ModelSerializer):
    # Buteur
    player_name       = serializers.SerializerMethodField()
    player_short_name = serializers.SerializerMethodField()
    player_photo      = serializers.SerializerMethodField()

    # Club du but
    club_name = serializers.SerializerMethodField()
    club_logo = serializers.SerializerMethodField()

    # Passeur
    assist_name         = serializers.SerializerMethodField()
    assist_short_name   = serializers.SerializerMethodField()
    assist_player_photo = serializers.SerializerMethodField()

    # Drapeaux utiles
    is_penalty  = serializers.SerializerMethodField()
    is_own_goal = serializers.SerializerMethodField()
    type        = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = "__all__"

    # ----- Buteur -----
    def get_player_name(self, obj):
        p = getattr(obj, "player", None)
        if p:
            full = getattr(p, "name", None) or f"{getattr(p,'first_name','')} {getattr(p,'last_name','')}".strip()
            return full or f"Joueur #{getattr(p,'pk','')}"
        fn = getattr(obj, "player_first_name", "") or ""
        ln = getattr(obj, "player_last_name", "") or ""
        full = f"{fn} {ln}".strip()
        return full or None

    def get_player_short_name(self, obj):
        return _short_name(self.get_player_name(obj))

    def get_player_photo(self, obj):
        request = self.context.get("request")
        p = getattr(obj, "player", None)
        file_or_url = getattr(p, "photo", None) if p else None
        return _abs_any(request, file_or_url)

    # ----- Club -----
    def get_club_name(self, obj):
        c = getattr(obj, "club", None)
        return getattr(c, "name", None) if c else None

    def get_club_logo(self, obj):
        request = self.context.get("request")
        c = getattr(obj, "club", None)
        file_or_url = getattr(c, "logo", None) if c else None
        return _abs_any(request, file_or_url)

    # ----- Passeur -----
    def get_assist_name(self, obj):
        # priorité à assist_name libre
        if getattr(obj, "assist_name", None):
            return obj.assist_name
        # fallback éventuels
        if getattr(obj, "assist", None):
            return obj.assist
        ap = getattr(obj, "assist_player", None)
        if ap:
            return getattr(ap, "name", None) or f"{getattr(ap,'first_name','')} {getattr(ap,'last_name','')}".strip()
        fn = getattr(obj, "assist_player_first_name", "") or ""
        ln = getattr(obj, "assist_player_last_name", "") or ""
        full = f"{fn} {ln}".strip()
        return full or None

    def get_assist_short_name(self, obj):
        return _short_name(self.get_assist_name(obj))

    def get_assist_player_photo(self, obj):
        """
        Photo réelle du passeur (si FK assist_player présent).
        Sert au front pour l’icône 'crampon' avec la tête du passeur.
        """
        request = self.context.get("request")
        ap = getattr(obj, "assist_player", None)
        file_or_url = getattr(ap, "photo", None) if ap else None
        return _abs_any(request, file_or_url)

    # ----- Flags -----
    def get_is_penalty(self, obj):
        for n in ("is_penalty", "penalty", "on_penalty"):
            if hasattr(obj, n):
                return bool(getattr(obj, n))
        t = (getattr(obj, "type", "") or getattr(obj, "kind", "") or "").upper()
        return t in {"PEN", "P", "PK", "PENALTY"}

    def get_is_own_goal(self, obj):
        for n in ("is_own_goal", "own_goal", "og"):
            if hasattr(obj, n):
                return bool(getattr(obj, n))
        t = (getattr(obj, "type", "") or getattr(obj, "kind", "") or "").upper()
        return t in {"OG", "CSC", "OWN_GOAL", "OWNGOAL"}

    def get_type(self, obj):
        return getattr(obj, "type", None) or getattr(obj, "kind", None)


# ---------- CARDS ----------
class CardSerializer(serializers.ModelSerializer):
    player_name            = serializers.SerializerMethodField()
    card_player_short_name = serializers.SerializerMethodField()
    club_name              = serializers.SerializerMethodField()
    club_logo              = serializers.SerializerMethodField()
    player_photo           = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = "__all__"

    def get_player_name(self, obj):
        p = getattr(obj, "player", None)
        if p:
            full = getattr(p, "name", None) or f"{getattr(p,'first_name','')} {getattr(p,'last_name','')}".strip()
            return full or f"Joueur #{getattr(p,'pk','')}"
        fn = getattr(obj, "player_first_name", "") or ""
        ln = getattr(obj, "player_last_name", "") or ""
        full = f"{fn} {ln}".strip()
        return full or None

    def get_card_player_short_name(self, obj):
        return _short_name(self.get_player_name(obj))

    def get_player_photo(self, obj):
        request = self.context.get("request")
        p = getattr(obj, "player", None)
        file_or_url = getattr(p, "photo", None) if p else None
        return _abs_any(request, file_or_url)

    def get_club_name(self, obj):
        c = getattr(obj, "club", None)
        return getattr(c, "name", None) if c else None

    def get_club_logo(self, obj):
        request = self.context.get("request")
        c = getattr(obj, "club", None)
        file_or_url = getattr(c, "logo", None) if c else None
        return _abs_any(request, file_or_url)


# ---------- LINEUPS (read serializer) ----------
class LineupSerializer(serializers.ModelSerializer):
    """
    Schéma plat attendu par le front.
    """
    club_name      = serializers.CharField(source="club.name", read_only=True)
    club_logo      = serializers.SerializerMethodField()
    player_display = serializers.SerializerMethodField()
    player_photo   = serializers.SerializerMethodField()
    rating         = serializers.SerializerMethodField()  # clé attendue par le front

    class Meta:
        model = Lineup
        fields = [
            "id", "match", "club", "club_name", "club_logo",
            "player", "player_name", "player_display",
            "number", "position", "is_starting", "is_captain",
            "rating",
            "player_photo",
        ]

    def _abs_any_local(self, request, value):
        if not value:
            return None
        try:
            url = value.url
        except Exception:
            url = None
        if url is None:
            url = str(value).strip()
            if not url:
                return None
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return request.build_absolute_uri(url) if request else url

    def get_club_logo(self, obj):
        request = self.context.get("request")
        club = getattr(obj, "club", None)
        return self._abs_any_local(request, getattr(club, "logo", None) if club else None)

    def get_player_display(self, obj):
        # priorité au champ libre
        name = getattr(obj, "player_name", None)
        if name:
            name = str(name).strip()
            if name:
                return name
        # sinon nom joueur FK
        p = getattr(obj, "player", None)
        if not p:
            return None
        full = getattr(p, "name", None)
        if full:
            full = str(full).strip()
            return full or None
        fn = (getattr(p, "first_name", "") or "").strip()
        ln = (getattr(p, "last_name", "") or "").strip()
        full = f"{fn} {ln}".strip()
        return full or None

    def get_player_photo(self, obj):
        request = self.context.get("request")
        # 1) photo custom sur la ligne
        photo_line = getattr(obj, "photo", None)
        url = self._abs_any_local(request, photo_line)
        if url:
            return url
        # 2) photo du Player lié
        p = getattr(obj, "player", None)
        return self._abs_any_local(request, getattr(p, "photo", None) if p else None)

    def get_rating(self, obj):
        """
        Retourne une note numérique (float) ou None.
        """
        try:
            val = getattr(obj, "rating", None)
            if val in (None, "") and hasattr(obj, "note"):
                val = getattr(obj, "note", None)
            if isinstance(val, str):
                val = val.replace(",", ".").strip()
            x = float(val)
            return x
        except Exception:
            return None


# ---------- LINEUPS (write serializer) ----------
class LineupWriteSerializer(serializers.ModelSerializer):
    # alias d’entrée "note"
    note = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = Lineup
        fields = [
            "id", "match", "club", "player", "player_name",
            "number", "position", "is_starting", "is_captain",
            "rating", "note", "photo",
        ]
        extra_kwargs = {
            "match": {"required": False},
            "club": {"required": False},
            "player": {"required": False},
            "player_name": {"required": False},
            "number": {"required": False},
            "position": {"required": False},
            "is_starting": {"required": False},
            "is_captain": {"required": False},
            "rating": {"required": False},
            "photo": {"required": False},
        }

    def _coerce_rating(self, val):
        if val in (None, ""):
            return None
        if isinstance(val, str):
            val = val.replace(",", ".").strip()
        try:
            return round(float(val), 1)
        except Exception:
            return None

    def validate(self, attrs):
        raw_note = self.initial_data.get("note", None)
        raw_rating = attrs.get("rating", None)

        if raw_rating in (None, "") and raw_note not in (None, ""):
            coerced = self._coerce_rating(raw_note)
            if coerced is not None:
                attrs["rating"] = coerced

        if "rating" in attrs:
            attrs["rating"] = self._coerce_rating(attrs["rating"])

        # minutes_played ignoré
        attrs.pop("minutes_played", None)

        return attrs


# ---------- TEAM INFO ----------
class TeamInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamInfoPerMatch
        fields = ["id", "match", "club", "formation", "coach_name"]

# rétro-compat
TeamInfoPerMatchSerializer = TeamInfoSerializer


# ---------- TEAM LINEUP WRAPPER ----------
class TeamLineupSerializer(serializers.Serializer):
    club_id = serializers.IntegerField()
    club_name = serializers.CharField()
    players = serializers.SerializerMethodField()
    team_avg_rating = serializers.SerializerMethodField()

    def get_players(self, obj):
        from .serializers import LineupSerializer
        items = obj.get("players", [])
        return LineupSerializer(items, many=True, context=self.context).data

    def get_team_avg_rating(self, obj):
        raw_players = obj.get("players", []) or []
        ratings = []

        # déjà sérialisés ?
        if raw_players and isinstance(raw_players[0], dict):
            for d in raw_players:
                r = d.get("rating", None)
                if r is not None:
                    try:
                        ratings.append(float(r))
                    except Exception:
                        pass
        else:
            from .serializers import LineupSerializer
            ls = LineupSerializer(raw_players, many=True, context=self.context)
            for d in ls.data:
                r = d.get("rating", None)
                if r is not None:
                    try:
                        ratings.append(float(r))
                    except Exception:
                        pass

        if not ratings:
            return None
        return round(sum(ratings) / len(ratings), 2)


# ---------- MATCH ----------
class MatchSerializer(serializers.ModelSerializer):
    goals = serializers.SerializerMethodField()
    cards = serializers.SerializerMethodField()

    round_name    = serializers.CharField(source="round.name", read_only=True)
    round_number  = serializers.IntegerField(source="round.number", read_only=True)

    home_club_name = serializers.CharField(source="home_club.name", read_only=True)
    away_club_name = serializers.CharField(source="away_club.name", read_only=True)
    home_club_logo = serializers.SerializerMethodField()
    away_club_logo = serializers.SerializerMethodField()

    home_formation  = serializers.SerializerMethodField()
    away_formation  = serializers.SerializerMethodField()
    home_coach_name = serializers.SerializerMethodField()
    away_coach_name = serializers.SerializerMethodField()

    # minute dynamique serveur
    current_minute  = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "round", "round_name", "round_number",
            "datetime",
            "home_club", "home_club_name", "home_club_logo",
            "away_club", "away_club_name", "away_club_logo",
            "home_score", "away_score",
            "status", "minute", "venue",
            "buteur",
            "current_minute",
            "home_formation", "away_formation",
            "home_coach_name", "away_coach_name",
            "goals", "cards",
        ]

    # logos clubs
    def get_home_club_logo(self, obj):
        request = self.context.get("request")
        club = getattr(obj, "home_club", None)
        file_or_url = getattr(club, "logo", None) if club else None
        return _abs_any(request, file_or_url)

    def get_away_club_logo(self, obj):
        request = self.context.get("request")
        club = getattr(obj, "away_club", None)
        file_or_url = getattr(club, "logo", None) if club else None
        return _abs_any(request, file_or_url)

    # events
    def get_goals(self, obj):
        mgr = getattr(obj, GOALS_REL_NAME, None)
        if mgr is not None and hasattr(mgr, "all"):
            qs = (
                mgr.all()
                .select_related("player", "club", "assist_player")
                .order_by("minute", "id")
            )
        else:
            qs = (
                Goal.objects.filter(match=obj)
                .select_related("player", "club", "assist_player")
                .order_by("minute", "id")
            )
        return GoalSerializer(qs, many=True, context=self.context).data

    def get_cards(self, obj):
        mgr = getattr(obj, CARDS_REL_NAME, None)
        if mgr is not None and hasattr(mgr, "all"):
            qs = mgr.all().select_related("player", "club").order_by("minute", "id")
        else:
            qs = (
                Card.objects.filter(match=obj)
                .select_related("player", "club")
                .order_by("minute", "id")
            )
        return CardSerializer(qs, many=True, context=self.context).data

    # team info (formation / coach)
    def _team_info_map(self, obj):
        """
        Cache local pour éviter 2 requêtes TeamInfoPerMatch.
        """
        cache_key = f"_ti_cache_{id(obj)}"
        ctx = self.context
        if cache_key in ctx:
            return ctx[cache_key]

        infos = TeamInfoPerMatch.objects.filter(match=obj)
        mapping = {ti.club_id: ti for ti in infos}
        ctx[cache_key] = mapping
        return mapping

    def get_home_formation(self, obj):
        mapping = self._team_info_map(obj)
        ti = mapping.get(getattr(obj, "home_club_id", None))
        return getattr(ti, "formation", "") if ti else ""

    def get_away_formation(self, obj):
        mapping = self._team_info_map(obj)
        ti = mapping.get(getattr(obj, "away_club_id", None))
        return getattr(ti, "formation", "") if ti else ""

    def get_home_coach_name(self, obj):
        mapping = self._team_info_map(obj)
        ti = mapping.get(getattr(obj, "home_club_id", None))
        return getattr(ti, "coach_name", "") if ti else ""

    def get_away_coach_name(self, obj):
        mapping = self._team_info_map(obj)
        ti = mapping.get(getattr(obj, "away_club_id", None))
        return getattr(ti, "coach_name", "") if ti else ""

    # minute dynamique serveur
    def get_current_minute(self, obj):
        """
        Renvoie un ENTIER représentant la minute actuelle du match.
        On fait en sorte de TOUJOURS retourner un entier stable.

        Règles d'affichage foot:
          - HT / PAUSED       => 45
          - FT / FINISHED     => 90
          - LIVE 2e MT        => max(46, 45 + floor((now - kickoff_2)/60)), clamp à 90
          - LIVE 1ère MT      => max(0, floor((now - kickoff_1)/60)), clamp à 90
          - sinon             => minute manuelle (ou 0)
        """
        status = (getattr(obj, "status", "") or "").upper()
        now = timezone.now()

        # Mi-temps / pause
        if status in ["HT", "PAUSED"]:
            return 45

        # Terminé
        if status in ["FT", "FINISHED"]:
            return 90

        if status == "LIVE":
            kickoff_2 = getattr(obj, "kickoff_2", None)
            kickoff_1 = getattr(obj, "kickoff_1", None)

            # 2e mi-temps
            if kickoff_2:
                diff_seconds = (now - kickoff_2).total_seconds()
                raw_minute = 45 + int(diff_seconds // 60)

                if raw_minute < 46:
                    raw_minute = 46
                if raw_minute > 90:
                    raw_minute = 90

                return raw_minute

            # 1ère mi-temps
            if kickoff_1:
                diff_seconds = (now - kickoff_1).total_seconds()
                raw_minute = int(diff_seconds // 60)

                if raw_minute < 0:
                    raw_minute = 0
                if raw_minute > 90:
                    raw_minute = 90

                return raw_minute

            # LIVE mais pas de kickoff_* (match créé à la main sans transition correcte)
            # -> fallback minute manuelle ou 0
            try:
                return int(getattr(obj, "minute", 0) or 0)
            except Exception:
                return 0

        # pas LIVE : fallback minute manuelle
        try:
            return int(getattr(obj, "minute", 0) or 0)
        except Exception:
            return 0
