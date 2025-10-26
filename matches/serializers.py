# matches/serializers.py
from rest_framework import serializers
from django.utils import timezone  # ⬅️ ajouté

from .models import (
    Match, Goal, Card, Round,
    Lineup, TeamInfoPerMatch,
)

# Managers inverses dynamiques (goals/cards) – robustes si related_name change
GOALS_REL_NAME = Goal._meta.get_field("match").remote_field.get_accessor_name()
CARDS_REL_NAME = Card._meta.get_field("match").remote_field.get_accessor_name()


# ---------- Helpers ----------
def _abs_any(request, value):
    """
    Retourne une URL absolue quelle que soit la nature du champ :
    - Image/FileField -> .url
    - str/URLField (déjà absolue ou relative) -> retourne tel quel (absolutise si besoin)
    """
    if not value:
        return None

    # 1) File/Image field object
    try:
        url = value.url  # ex: FieldFile
    except Exception:
        url = None

    # 2) String/URLField
    if url is None:
        url = str(value).strip()
        if not url:
            return None

    # Absolutise si besoin
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return request.build_absolute_uri(url) if request else url


# Nom abrégé "A. Diallo"
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
    assist_name          = serializers.SerializerMethodField()
    assist_short_name    = serializers.SerializerMethodField()
    assist_player_photo  = serializers.SerializerMethodField()  # ⬅️ NOUVEAU

    # Drapeaux utiles
    is_penalty  = serializers.SerializerMethodField()
    is_own_goal = serializers.SerializerMethodField()
    type        = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = "__all__"   # inclut les champs du modèle + nos SerializerMethodField déclarés ci-dessus

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
        if getattr(obj, "assist_name", None):
            return obj.assist_name
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
    - 'rating' est calculé de manière robuste (lineup.rating, puis lineup.note si présent)
    - 'player_photo' renvoie une URL absolue si possible
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
            # minutes_played supprimé côté lecture
            "rating",
            "player_photo",
        ]

    # utilitaire absolu (tolère FieldFile ou str)
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
        # priorité au champ libre de la ligne
        name = getattr(obj, "player_name", None)
        if name:
            name = str(name).strip()
            if name:
                return name
        # sinon, on compose depuis Player
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
        # 1) photo stockée sur la ligne (si tu l'utilises)
        photo_line = getattr(obj, "photo", None)
        url = self._abs_any_local(request, photo_line)
        if url:
            return url
        # 2) photo du Player lié
        p = getattr(obj, "player", None)
        return self._abs_any_local(request, getattr(p, "photo", None) if p else None)

    def get_rating(self, obj):
        """
        Lis, dans cet ordre, la note sous forme numérique :
          - Lineup.rating (Decimal/float/str)
          - Lineup.note (si le champ existe en DB / ou injecté côté queryset)
        Accepte '6,8' -> 6.8. Ne jette jamais d'exception, retourne None sinon.
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
    """
    Serializer utilisé pour CREATE/UPDATE/PATCH.
    - 'rating' devient écrivable.
    - 'note' (alias) accepté en entrée et mappé vers 'rating'.
    - minutes_played ignoré (non requis et non validé).
    """
    # alias d’entrée: permet d’envoyer {"note": 6.8} au lieu de {"rating": 6.8}
    note = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = Lineup
        fields = [
            "id", "match", "club", "player", "player_name",
            "number", "position", "is_starting", "is_captain",
            "rating", "note", "photo",
            # minutes_played retiré côté écriture
        ]
        extra_kwargs = {
            # sur PATCH partiel, rien n'est strictement requis
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
        # map 'note' -> 'rating' si rating absent
        raw_note = self.initial_data.get("note", None)
        raw_rating = attrs.get("rating", None)
        if raw_rating in (None, "") and raw_note not in (None, ""):
            coerced = self._coerce_rating(raw_note)
            if coerced is not None:
                attrs["rating"] = coerced
        # normaliser rating si fourni
        if "rating" in attrs:
            attrs["rating"] = self._coerce_rating(attrs["rating"])

        # minutes_played totalement ignoré
        attrs.pop("minutes_played", None)

        return attrs


# ---------- TEAM INFO ----------
class TeamInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamInfoPerMatch
        fields = ["id", "match", "club", "formation", "coach_name"]

# Rétro-compatibilité d'import
TeamInfoPerMatchSerializer = TeamInfoSerializer


# ---------- TEAM LINEUP WRAPPER (pour /lineups) ----------
class TeamLineupSerializer(serializers.Serializer):
    """
    Wrapper pour un côté (home/away) afin de calculer la moyenne d'équipe.
    Attendu sous forme de dict :
    {
      "club_id": int,
      "club_name": str,
      "players": <QuerySet[Lineup]> | [Lineup] | [dict déjà sérialisé]
    }
    """
    club_id = serializers.IntegerField()
    club_name = serializers.CharField()
    players = serializers.SerializerMethodField()
    team_avg_rating = serializers.SerializerMethodField()

    def get_players(self, obj):
        from .serializers import LineupSerializer  # safe: résolu au runtime
        items = obj.get("players", [])
        return LineupSerializer(items, many=True, context=self.context).data

    def get_team_avg_rating(self, obj):
        raw_players = obj.get("players", []) or []
        ratings = []

        # si ce sont des dicts déjà passés par LineupSerializer
        if raw_players and isinstance(raw_players[0], dict):
            for d in raw_players:
                r = d.get("rating", None)
                if r is not None:
                    try:
                        ratings.append(float(r))
                    except Exception:
                        pass
        else:
            from .serializers import LineupSerializer  # import tardif
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

    # Expose formation + coach côté match (lu dans TeamInfoPerMatch)
    home_formation   = serializers.SerializerMethodField()
    away_formation   = serializers.SerializerMethodField()
    home_coach_name  = serializers.SerializerMethodField()
    away_coach_name  = serializers.SerializerMethodField()

    # 👇 NOUVEAU: minute officielle calculée côté serveur
    current_minute   = serializers.SerializerMethodField()

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
            # minute calculée côté serveur
            "current_minute",
            # team info exposées au front:
            "home_formation", "away_formation",
            "home_coach_name", "away_coach_name",
            # events:
            "goals", "cards",
        ]

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

    # ---- events ----
    def get_goals(self, obj):
        mgr = getattr(obj, GOALS_REL_NAME, None)
        if mgr is not None and hasattr(mgr, "all"):
            qs = (
                mgr.all()
                .select_related("player", "club", "assist_player")  # ⬅️ assist_player préchargé
                .order_by("minute", "id")
            )
        else:
            qs = (
                Goal.objects.filter(match=obj)
                .select_related("player", "club", "assist_player")  # ⬅️ idem
                .order_by("minute", "id")
            )
        return GoalSerializer(qs, many=True, context=self.context).data

    def get_cards(self, obj):
        mgr = getattr(obj, CARDS_REL_NAME, None)
        if mgr is not None and hasattr(mgr, "all"):
            qs = mgr.all().select_related("player", "club").order_by("minute", "id")
        else:
            qs = Card.objects.filter(match=obj).select_related("player", "club").order_by("minute", "id")
        return CardSerializer(qs, many=True, context=self.context).data

    # ---- team info (formation / coach) ----
    def _team_info_map(self, obj):
        """
        Retourne {club_id: TeamInfoPerMatch} pour ce match,
        mis en cache dans le contexte du serializer (évite double requête).
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

    # ---- minute officielle serveur ----
    def get_current_minute(self, obj):
        """
        But: donner une minute cohérente pour TOUS les clients sans qu'ils la fassent évoluer tous seuls.
        Règle:
          - "LIVE" => calcule minute actuelle à partir de kickoff_1 / kickoff_2
          - "HT" ou "PAUSED" => renvoie 45
          - "FT"/"FINISHED" => renvoie 90
          - sinon => None
        Conditions:
          - Le modèle Match doit avoir kickoff_1 (DateTimeField) = début 1ère MT,
            kickoff_2 (DateTimeField, nullable) = début 2ème MT.
        """
        status = (getattr(obj, "status", "") or "").upper()
        now = timezone.now()

        # mi-temps / pause -> figé à 45'
        if status in ["HT", "PAUSED"]:
            return 45

        # match terminé -> figé à 90' (ou None si tu préfères rien afficher)
        if status in ["FT", "FINISHED"]:
            return 90

        # match en cours -> calcul dynamique
        if status == "LIVE":
            kickoff_2 = getattr(obj, "kickoff_2", None)
            kickoff_1 = getattr(obj, "kickoff_1", None)

            # Si on a une heure de reprise 2e mi-temps
            if kickoff_2:
                diff_seconds = (now - kickoff_2).total_seconds()
                raw_minute = 45 + int(diff_seconds // 60)
                # protège contre valeurs trop petites
                return max(46, raw_minute)

            # Sinon on est en 1ère mi-temps
            if kickoff_1:
                diff_seconds = (now - kickoff_1).total_seconds()
                raw_minute = int(diff_seconds // 60)
                return max(0, raw_minute)

        # par défaut
        return None
