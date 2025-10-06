# matches/stats.py
from collections import defaultdict
from django.db.models import Q

from .models import Goal, Card, Match

def _fullname(player) -> str:
    # essaie player.name, sinon "first last"
    if getattr(player, "name", None):
        return (player.name or "").strip()
    return f"{getattr(player,'first_name','')} {getattr(player,'last_name','')}".strip()

def _q_is_own_goal():
    """Filtre robuste pour détecter un csc, quel que soit le champ que tu utilises."""
    return (
        Q(own_goal=True) |
        Q(type__in=["OG","Csc","CSC","OWN_GOAL","OWNGOAL"])
    )

def _q_name_equals(field, full_name: str):
    """Match insensible à la casse sur un champ texte (player_name / assist_name)."""
    if not full_name:
        # jamais vrai
        return Q(pk__in=[])
    return Q(**{f"{field}__iexact": full_name})

def compute_club_player_stats(club, *, season=None, competition=None):
    """
    Retourne un dict {player_id: {"goals": n, "assists": n, "yc": n, "rc": n}}
    construit ***exactement*** comme les classements (FK OU nom).
    """
    # Base: tous les matches où ce club a joué
    m_q = Q(home_club=club) | Q(away_club=club)
    if season is not None:
        m_q &= Q(round__season=season) | Q(season=season)
    if competition is not None:
        m_q &= Q(round__competition=competition) | Q(competition=competition)
    match_ids = list(Match.objects.filter(m_q).values_list("id", flat=True))

    stats = defaultdict(lambda: {"goals": 0, "assists": 0, "yc": 0, "rc": 0})

    # ---- BUTS (club concerné) ----
    g_q = Q(match_id__in=match_ids) & Q(club=club) & ~_q_is_own_goal()
    for g in Goal.objects.filter(g_q).select_related("player", "assist_player"):
        # buteur par FK ou par nom
        if g.player_id:
            pid = g.player_id
        else:
            pid = None
            # essaie d’associer par nom plein (cas de saisie "au nom")
            for p in club.players.all():  # si le modèle s'appelle autrement, adapte
                if _fullname(p) and str(g.player_name or "").strip().lower() == _fullname(p).lower():
                    pid = p.id
                    break
        if pid:
            stats[pid]["goals"] += 1

        # passe décisive par FK ou par nom
        if g.assist_player_id:
            stats[g.assist_player_id]["assists"] += 1
        else:
            a_name = (g.assist_name or "").strip().lower()
            if a_name:
                for p in club.players.all():
                    if _fullname(p) and a_name == _fullname(p).lower():
                        stats[p.id]["assists"] += 1
                        break

    # ---- CARTONS (peu importe home/away, on rattache par FK ou nom) ----
    from .models import Card
    c_q = Q(match_id__in=match_ids) & Q(club=club)
    for c in Card.objects.filter(c_q).select_related("player"):
        # rattache joueur
        pid = c.player_id
        if not pid:
            c_name = (c.player_name or "").strip().lower()
            if c_name:
                for p in club.players.all():
                    if _fullname(p) and c_name == _fullname(p).lower():
                        pid = p.id
                        break
        if not pid:
            continue

        color = (c.color or c.type or "").upper()
        if color.startswith("R"):
            stats[pid]["rc"] += 1
        else:  # défaut: jaune
            stats[pid]["yc"] += 1

    return stats
