# matches/admin.py
from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

from .models import Match, Goal, Card, Round
from clubs.models import Club
from players.models import Player

# Ces imports sont protégés au cas où tes modèles ne sont pas encore créés
try:
    from .models import Lineup, TeamInfoPerMatch
except Exception:  # Lineup/TeamInfoPerMatch pas encore définis
    Lineup = None
    TeamInfoPerMatch = None


def has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())


# ---------- Inlines événements ----------
class GoalInline(admin.TabularInline):
    model = Goal
    extra = 0
    raw_id_fields = ("club", "player", "assist_player")

    def get_fields(self, request, obj=None):
        fields = ["minute", "club", "player"]
        if has_field(Goal, "assist_player"):
            fields.append("assist_player")
        return fields


class CardInline(admin.TabularInline):
    """
    Modèle courant a 'type' (Y/R). On l'affiche toujours,
    et on ajoute d'éventuels alias ('color', 'card_type') si présents.
    """
    model = Card
    extra = 0
    raw_id_fields = ("club", "player")

    def get_fields(self, request, obj=None):
        fields = ["minute", "club", "player"]
        if has_field(Card, "type"):
            fields.append("type")
        if has_field(Card, "color"):
            fields.append("color")
        if has_field(Card, "card_type"):
            fields.append("card_type")
        return fields


# ---------- Inlines Compo & Infos d'équipe ----------
if Lineup:
    class LineupInlineForm(forms.ModelForm):
        class Meta:
            model = Lineup
            fields = (
                "club", "player", "player_name",
                "number", "position",
                "is_starting", "is_captain",
                "rating",        # ⬅️ minutes_played retiré
                "photo",
            )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Limiter la liste des clubs aux 2 clubs du match courant
            obj = getattr(getattr(self, "admin_site", None), "_current_match_obj", None)
            if obj is None:
                obj = getattr(self, "_match_obj", None)

            if obj and "club" in self.fields:
                self.fields["club"].queryset = Club.objects.filter(
                    id__in=[obj.home_club_id, obj.away_club_id]
                )

            # Filtrer les joueurs par club sélectionné
            club_id = None
            if "club" in self.data:
                try:
                    club_id = int(self.data.get(self.add_prefix("club")) or 0)
                except Exception:
                    club_id = None
            if not club_id:
                club_id = getattr(getattr(self.instance, "club", None), "id", None)

            if "player" in self.fields:
                qs = Player.objects.all().order_by("name", "first_name", "last_name", "id")
                if club_id:
                    qs = qs.filter(club_id=club_id)
                self.fields["player"].queryset = qs

            if "rating" in self.fields:
                self.fields["rating"].help_text = "1.0 à 10.0 (laisser vide si pas de note)."

        def clean(self):
            cleaned = super().clean()
            rating = cleaned.get("rating", None)

            # Accepte "6,8"
            if isinstance(rating, str):
                try:
                    rating = rating.replace(",", ".").strip()
                    rating = float(rating)
                    cleaned["rating"] = rating
                except Exception:
                    raise ValidationError({"rating": "Valeur de note invalide."})

            # Borne 1.0–10.0 si note fournie
            if rating not in (None, ""):
                try:
                    rf = float(rating)
                except Exception:
                    raise ValidationError({"rating": "Valeur de note invalide."})
                if not (1.0 <= rf <= 10.0):
                    raise ValidationError({"rating": "Le rating doit être entre 1.0 et 10.0."})
                cleaned["rating"] = round(rf, 1)

            return cleaned

    class LineupInline(admin.TabularInline):
        """
        Saisie rapide des compositions (titulaires + remplaçants) sur la fiche Match.
        - ajoute Rating (note)
        - ajoute Capitaine
        - permet de sélectionner un joueur filtré par club
        """
        model = Lineup
        form = LineupInlineForm
        extra = 0
        fields = (
            "club", "player", "player_name",
            "number", "position",
            "is_starting", "is_captain",
            "rating",     # ⬅️ plus de minutes ici
        )
        raw_id_fields = ("club", "player")
        show_change_link = True

        def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
            # Limite le choix du club aux 2 clubs du match
            if db_field.name == "club" and hasattr(request, "_obj_") and request._obj_:
                obj = request._obj_
                kwargs["queryset"] = Club.objects.filter(id__in=[obj.home_club_id, obj.away_club_id])
            return super().formfield_for_foreignkey(db_field, request, **kwargs)

        class Media:
            js = ("admin/lineup_inline_filter.js",)

if TeamInfoPerMatch:
    class TeamInfoPerMatchInline(admin.StackedInline):
        """
        Saisie formation + coach pour chaque club du match (max 2 lignes).
        """
        model = TeamInfoPerMatch
        extra = 0
        min_num = 0
        max_num = 2
        fields = ("club", "formation", "coach_name")
        verbose_name = "Infos d'équipe (formation/coach)"
        verbose_name_plural = "Infos d'équipe (formation/coach)"

        def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
            if db_field.name == "club" and hasattr(request, "_obj_") and request._obj_:
                obj = request._obj_
                kwargs["queryset"] = Club.objects.filter(id__in=[obj.home_club_id, obj.away_club_id])
            return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ---------- Admin Match ----------
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "round",
        "datetime",
        "home_club",
        "home_score",
        "away_score",
        "away_club",
        "status",
        "minute",
    )
    list_filter = ("status", "round", "datetime")
    search_fields = ("home_club__name", "away_club__name", "venue")
    date_hierarchy = "datetime"

    inlines = []
    if TeamInfoPerMatch:
        inlines.append(TeamInfoPerMatchInline)
    if Lineup:
        inlines.append(LineupInline)
    inlines += [GoalInline, CardInline]

    def get_form(self, request, obj=None, **kwargs):
        # Rendez l'objet match disponible aux inlines pour filtrage
        request._obj_ = obj
        if Lineup:
            LineupInlineForm._match_obj = obj
        return super().get_form(request, obj, **kwargs)

    change_list_template = "admin/matches/change_list.html"


# ---------- Admin Lineup (écran dédié) ----------
if Lineup:
    class LineupAdminForm(forms.ModelForm):
        class Meta:
            model = Lineup
            fields = "__all__"

        def clean(self):
            cleaned = super().clean()
            rating = cleaned.get("rating", None)

            if isinstance(rating, str):
                try:
                    rating = float(rating.replace(",", ".").strip())
                except Exception:
                    raise ValidationError({"rating": "Valeur de note invalide."})

            if rating not in (None, ""):
                if not (1.0 <= float(rating) <= 10.0):
                    raise ValidationError({"rating": "Le rating doit être entre 1.0 et 10.0."})
                cleaned["rating"] = round(float(rating), 1)
            return cleaned

    @admin.register(Lineup)
    class LineupAdmin(admin.ModelAdmin):
        form = LineupAdminForm
        list_display = (
            "match", "club", "player", "player_name",
            "number", "position", "is_starting", "is_captain",
            "rating",     # ⬅️ minutes_played retiré
        )
        list_filter = ("match", "club", "is_starting", "is_captain")
        search_fields = ("player_name", "player__name", "player__first_name", "player__last_name")
        raw_id_fields = ("match", "club", "player")
        list_editable = ("rating", "is_captain", "is_starting")  # ⬅️ minutes_played retiré

        def formfield_for_foreignkey(self, db_field, request, **kwargs):
            if db_field.name == "player":
                club_val = (request.POST.get("club") or request.GET.get("club") or "").strip()
                if club_val.isdigit():
                    kwargs["queryset"] = Player.objects.filter(club_id=int(club_val))
            return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ---------- Admin TeamInfoPerMatch (écran dédié) ----------
if TeamInfoPerMatch:
    @admin.register(TeamInfoPerMatch)
    class TeamInfoPerMatchAdmin(admin.ModelAdmin):
        list_display = ("match", "club", "formation", "coach_name")
        list_filter = ("club",)
        search_fields = ("coach_name", "formation", "match__home_club__name", "match__away_club__name")


# ---------- Admin Goal ----------
@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    ordering = ("-id",)

    def get_list_display(self, request):
        cols = ["id", "match", "club", "minute", "player"]
        if has_field(Goal, "assist_player"):
            cols.append("assist_player")
        return cols

    list_filter = ("club", "match")
    search_fields = (
        "player__name",
        "player__first_name",
        "player__last_name",
        "assist_player__name",
        "assist_player__first_name",
        "assist_player__last_name",
    )

    def get_raw_id_fields(self, request):
        ids = ["match", "club", "player"]
        if has_field(Goal, "assist_player"):
            ids.append("assist_player")
        return ids

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        m = request.GET.get("match")
        c = request.GET.get("club")
        minute = request.GET.get("minute")
        if m and m.isdigit():
            initial["match"] = int(m)
        if c and c.isdigit():
            initial["club"] = int(c)
        if minute and minute.isdigit():
            initial["minute"] = int(minute)
        return initial


# ---------- Admin Card ----------
@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    ordering = ("-id",)

    def get_list_display(self, request):
        cols = ["id", "match", "club", "minute", "player"]
        if has_field(Card, "type"):
            cols.append("type")
        if has_field(Card, "color"):
            cols.append("color")
        if has_field(Card, "card_type"):
            cols.append("card_type")
        return cols

    def get_list_filter(self, request):
        flt = ["club", "match"]
        if has_field(Card, "type"):
            flt.insert(0, "type")
        if has_field(Card, "color") and "color" not in flt:
            flt.insert(0, "color")
        return flt

    @property
    def list_filter(self):
        return self.get_list_filter(None)

    search_fields = (
        "player__name",
        "player__first_name",
        "player__last_name",
    )

    raw_id_fields = ("match", "club", "player")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        m = request.GET.get("match")
        c = request.GET.get("club")
        minute = request.GET.get("minute")
        color = request.GET.get("color")
        if m and m.isdigit():
            initial["match"] = int(m)
        if c and c.isdigit():
            initial["club"] = int(c)
        if minute and minute.isdigit():
            initial["minute"] = int(minute)
        if color and has_field(Card, "color"):
            initial["color"] = color
        return initial


# ---------- Admin Round ----------
@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "number", "date")
    search_fields = ("name",)
    ordering = ("id",)
