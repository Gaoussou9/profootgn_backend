# matches/utils/events.py
from __future__ import annotations
import re
from django.db import transaction
from clubs.models import Club
from players.models import Player
from matches.models import Match, Goal, Card

# Exemples acceptés :
#   "Gaoussou Cisse 12'"
#   "Diallo 45+2'"
#   "Camara 8; Bangoura 39' | Sylla 90+3"
_GOAL_RE = re.compile(r"""
    (?P<name>[^,\d;()]+?)\s*            # Nom joueur (tout sauf chiffres/ponctuation)
    (?P<min>\d{1,3})                    # Minute
    (?:\s*\+\s*(?P<add>\d{1,2}))?       # + temps additionnel éventuel
    \s*'?
""", re.VERBOSE | re.IGNORECASE)

# Exemples acceptés :
#   "Diallo 17 Y"
#   "Bah 23 r"
#   "Sylla 90+2 jaune"
_CARD_RE = re.compile(r"""
    (?P<name>[^,\d;()]+?)\s*
    (?P<min>\d{1,3})
    (?:\s*\+\s*(?P<add>\d{1,2}))?
    \s*'?
    \s*(?P<color>Y|J|JAUNE|YELLOW|R|ROUGE|RED)?
""", re.VERBOSE | re.IGNORECASE)

def _normalize_min(minute, add):
    base = int(minute or 0)
    if add:
        base += int(add)
    return max(0, base)

def _split_items(txt: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,|\n]+", str(txt or "")) if p.strip()]

def _parse_goals_text(txt: str, club: Club) -> list[dict]:
    out: list[dict] = []
    for part in _split_items(txt):
        m = _GOAL_RE.search(part)
        if not m:
            continue
        name = (m.group("name") or "").strip()
        minute = _normalize_min(m.group("min"), m.group("add"))
        out.append({"club": club.id, "minute": minute, "player_name": name})
    return out

def _parse_cards_text(txt: str, club: Club) -> list[dict]:
    out: list[dict] = []
    for part in _split_items(txt):
        m = _CARD_RE.search(part)
        if not m:
            continue
        name = (m.group("name") or "").strip()
        minute = _normalize_min(m.group("min"), m.group("add"))
        color_raw = (m.group("color") or "").upper()
        if color_raw in ("Y","J","JAUNE","YELLOW"):
            color = "Y"
        elif color_raw in ("R","ROUGE","RED"):
            color = "R"
        else:
            color = "Y"  # défaut : jaune
        out.append({"club": club.id, "minute": minute, "player_name": name, "type": color})
    return out

def _get_or_create_player_by_name(name: str, club: Club) -> Player | None:
    name = (name or "").strip()
    if not name:
        return None
    if hasattr(Player, "club"):
        p = Player.objects.filter(name__iexact=name, club=club).first()
        if p:
            return p
        p, _ = Player.objects.get_or_create(name=name, defaults={"club": club})
        if getattr(p, "club_id", None) is None:
            p.club = club
            p.save(update_fields=["club"])
        return p
    # Modèle sans champ club
    p, _ = Player.objects.get_or_create(name=name)
    return p

@transaction.atomic
def apply_events_from_text(
    match: Match,
    goals_home_txt: str | None,
    goals_away_txt: str | None,
    cards_home_txt: str | None,
    cards_away_txt: str | None,
    *,
    replace: bool = False,
):
    """Crée/replace les buts & cartons à partir de 4 zones texte."""
    if replace:
        Goal.objects.filter(match=match).delete()
        Card.objects.filter(match=match).delete()

    # Buteurs home
    for g in _parse_goals_text(goals_home_txt or "", match.home_club):
        player = _get_or_create_player_by_name(g["player_name"], match.home_club)
        Goal.objects.create(match=match, club=match.home_club, player=player, minute=g["minute"])

    # Buteurs away
    for g in _parse_goals_text(goals_away_txt or "", match.away_club):
        player = _get_or_create_player_by_name(g["player_name"], match.away_club)
        Goal.objects.create(match=match, club=match.away_club, player=player, minute=g["minute"])

    # Cartons home
    for c in _parse_cards_text(cards_home_txt or "", match.home_club):
        player = _get_or_create_player_by_name(c["player_name"], match.home_club)
        Card.objects.create(
            match=match, club=match.home_club, player=player, minute=c["minute"], type=c["type"]
        )

    # Cartons away
    for c in _parse_cards_text(cards_away_txt or "", match.away_club):
        player = _get_or_create_player_by_name(c["player_name"], match.away_club)
        Card.objects.create(
            match=match, club=match.away_club, player=player, minute=c["minute"], type=c["type"]
        )
