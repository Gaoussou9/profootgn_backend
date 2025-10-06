import django_filters as filters
from django.db import models
from .models import Match

class MatchFilter(django_filters.FilterSet):
    # on permet round_number, round_id, round (nom)
    round_number = django_filters.NumberFilter(field_name="round__number")
    round_id     = django_filters.NumberFilter(field_name="round_id")
    round        = django_filters.CharFilter(field_name="round__name", lookup_expr="iexact")


     class Meta:
        model  = Match
        fields = ["round_number", "round_id", "round", "status"]
        
    def filter_status(self, queryset, name, value):
        v = (value or "").strip().upper()
        if v == "LIVE":
            return queryset.filter(status__in=["LIVE", "HT", "PAUSED"])
        if v in {"FT", "FINISHED"}:
            return queryset.filter(status__in=["FT", "FINISHED"])
        if v in {"HT", "PAUSED"}:
            return queryset.filter(status__in=["HT", "PAUSED"])
        if v in {"SCHEDULED", "NOT_STARTED"}:
            return queryset.filter(status__in=["SCHEDULED", "NOT_STARTED"])
        if v == "POSTPONED":
            return queryset.filter(status="POSTPONED")
        if v == "SUSPENDED":
            return queryset.filter(status="SUSPENDED")
        if v in {"CANCELED", "CANCELLED"}:
            return queryset.filter(status="CANCELED")
        return queryset

    def filter_round_name(self, queryset, name, value):
        """
        Essaie d’interpréter 'J1', 'J 1', 'Journée 1', etc. -> cherche un Round.name qui contient '1'.
        Sinon, filtre par égalité insensible à la casse.
        """
        v = (value or "").strip()
        if not v:
            return queryset
        norm = v.lower().replace("journée", "j").replace(" ", "")
        # récupère la partie numérique si présente
        digits = "".join(ch for ch in norm if ch.isdigit())
        if digits:
            # ex: "1" -> cherche 'J1', 'Journée 1'... (contains insensible à la casse)
            return queryset.filter(round__name__icontains=digits)
        # fallback: égalité insensible à la casse sur le nom complet
        return queryset.filter(round__name__iexact=v)

    def filter_club(self, queryset, name, value):
        try:
            cid = int(value)
        except Exception:
            return queryset
        return queryset.filter(models.Q(home_club_id=cid) | models.Q(away_club_id=cid))
