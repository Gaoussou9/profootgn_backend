from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.db.models import Q, Case, When, Value, IntegerField
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseBadRequest

import json
import re

from clubs.models import Club
from players.models import Player
from .models import Match, Round, Goal, Card, Lineup, TeamInfoPerMatch


# ======================================
# Constantes & configuration
# ======================================

ADMIN_STATUSES = [
    ("SCHEDULED", "Non débuté"),
    ("LIVE",      "En cours"),
    ("HT",        "Mi-temps"),
    ("FT",        "Terminé"),
    ("SUSPENDED", "Suspendu"),
    ("POSTPONED", "Reporté"),
    ("CANCELED",  "Annulé"),
]

AUTO_CREATE_PLAYERS = getattr(settings, "PFOOT_AUTO_CREATE_PLAYERS", True)


# ======================================
# Helpers généraux
# ======================================

def _normalize_status(raw: str) -> str:
    s = (raw or "SCHEDULED").upper().strip()
    if s in {"POST", "POSTPONE", "POSTPONED"}: return "POSTPONED"
    if s in {"CAN", "CANCELLED", "CANCELED"}:  return "CANCELED"
    if s in {"FT", "FINISHED"}:                return "FT"
    if s in {"HT", "PAUSED"}:                  return "HT"
    if s in {"LIVE", "SCHEDULED", "SUSPENDED"}:return s
    return "SCHEDULED"

def _parse_dt(raw: str):
    if not raw: return timezone.now()
    dt = parse_datetime(raw)
    if not dt:  return timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt

def _to_int(s, default=0):
    try:
        return int(str(s).strip())
    except Exception:
        return default

def _resolve_club(value):
    if value is None: return None
    s = str(value).strip()
    if not s: return None
    if s.isdigit():
        return Club.objects.filter(pk=int(s)).first()
    club, _ = Club.objects.get_or_create(name=s)
    return club

def _normalize_card_color(raw: str) -> str:
    if not raw: return "Y"
    s = raw.strip().upper()
    if s in {"Y", "JAUNE", "YELLOW"}: return "Y"
    if s in {"R", "ROUGE", "RED"}:    return "R"
    return "Y"

def _extract_minute(token: str) -> int:
    if not token: return 0
    t = token.strip().replace("’", "'").replace("`", "'")
    t = t.replace("min", "").replace("'", "").replace("’", "")
    if "+" in t:
        base, add = t.split("+", 1)
        return _to_int(base) + _to_int(add)
    return _to_int(t)

def _model_has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False

def _field_max_len(model, name: str):
    try:
        f = model._meta.get_field(name)
        return getattr(f, "max_length", None)
    except Exception:
        return None

# ---- Clamp & normalisation poste ----
def _clamp_field(model, field: str, value: str) -> str:
    s = (value or "").strip()
    ml = _field_max_len(model, field)
    if ml is not None:
        s = s[:ml]
    return s

_POS_MAP = {
    "GARDIEN": "GK", "GOAL": "GK", "KEEPER": "GK", "GK": "GK",
    "DEFENSEUR": "DF", "DEF": "DF",
    "DC": "CB", "CB": "CB",
    "DG": "LB", "LB": "LB",
    "DD": "RB", "RB": "RB",
    "RWB": "RWB", "LWB": "LWB",
    "MILIEU": "CM", "M": "CM", "MC": "CM",
    "MOC": "AM", "MO": "AM", "AM": "AM",
    "MD": "RM", "RM": "RM",
    "MG": "LM", "LM": "LM",
    "AILIER": "W", "W": "W", "RW": "RW", "LW": "LW",
    "ATTAQUANT": "ST", "ATT": "ST", "BU": "ST", "AVANT": "ST", "ST": "ST",
    "CF": "CF", "DM": "DM",
}
def _normalize_position(val: str) -> str:
    if not val: return ""
    s = (val or "").strip().upper()
    return _POS_MAP.get(s, s)

def _set_card_color_kwargs(kwargs: dict, color_code: str) -> dict:
    c = (color_code or "Y").strip().upper()
    word = "YELLOW" if c == "Y" else "RED"

    def set_value(field: str, prefer_word=False):
        if not _model_has_field(Card, field):
            return
        ml = _field_max_len(Card, field)
        if ml is not None and ml <= 2:
            kwargs[field] = c
        else:
            kwargs[field] = word if prefer_word or (ml and ml >= 3) else c

    set_value("color"); set_value("card"); set_value("card_type", True); set_value("type")
    if _model_has_field(Card, "is_yellow"): kwargs["is_yellow"] = (c == "Y")
    if _model_has_field(Card, "is_red"):    kwargs["is_red"] = (c == "R")
    return kwargs

def _is_truthy(v):
    return (
        v is True
        or v == 1
        or (isinstance(v, str) and v.strip().lower() in {"1", "true", "yes", "y", "on"})
    )

def _set_goal_type_kwargs(kwargs: dict, is_penalty: bool, is_own_goal: bool, clear_when_false: bool = True) -> dict:
    for f in ("penalty", "is_penalty", "on_penalty"):
        if _model_has_field(Goal, f): kwargs[f] = bool(is_penalty)
    for f in ("own_goal", "is_own_goal", "og"):
        if _model_has_field(Goal, f): kwargs[f] = bool(is_own_goal)
    wanted = "PEN" if is_penalty else ("OG" if is_own_goal else "")
    for field in ("type", "kind"):
        if _model_has_field(Goal, field):
            ml = _field_max_len(Goal, field)
            val = wanted[:ml] if ml and wanted else wanted
            if wanted or clear_when_false: kwargs[field] = val
            break
    return kwargs

def _ensure_csc_fallback_kwargs(goal_kwargs: dict, is_own_goal: bool) -> dict:
    if not is_own_goal: return goal_kwargs
    has_store = any(_model_has_field(Goal, f) for f in ("own_goal", "is_own_goal", "og", "type", "kind"))
    if not has_store and _model_has_field(Goal, "assist_name"):
        goal_kwargs.setdefault("assist_name", "CSC")
    return goal_kwargs

# ---------- Rang d'affichage par poste ----------
def _position_rank_expr():
    """
    Expression ORM pour ordonner visuellement les titulaires :
    GK -> défense -> milieux -> ailes/attaque.
    """
    mapping = [
        ("GK", 0),
        ("RB", 10), ("RWB", 11),
        ("CB", 12),
        ("LB", 14), ("LWB", 15),
        ("DM", 20),
        ("CM", 21), ("MC", 21),
        ("AM", 22), ("MOC", 22),
        ("RW", 30), ("W", 30),
        ("ST", 31), ("CF", 31),
        ("LW", 32),
    ]
    whens = [When(position=pos, then=Value(rank)) for pos, rank in mapping]
    return Case(*whens, default=Value(999), output_field=IntegerField())


# ============ Rounds helpers ============

def _infer_round_number_from_name(name: str):
    if not name: return None
    s = str(name).lower()
    m = re.search(r"j(?:ourn[ée]e)?\s*(\d{1,3})", s)
    if m:
        try: return int(m.group(1))
        except Exception: return None
    m2 = re.search(r"\b(\d{1,3})\b", s)
    if m2:
        try: return int(m2.group(1))
        except Exception: return None
    return None

def _ensure_rounds_seeded(total=26):
    for r in Round.objects.all():
        if getattr(r, "number", None) in (None, 0):
            n = _infer_round_number_from_name(getattr(r, "name", "") or "")
            if n:
                try:
                    if not (r.name or "").strip():
                        r.name = f"J{n}"; r.save(update_fields=["number", "name"])
                    else:
                        r.number = n; r.save(update_fields=["number"])
                except Exception:
                    pass
    existing = set(Round.objects.filter(number__isnull=False).values_list("number", flat=True))
    for n in range(1, total + 1):
        if n in existing: continue
        try: Round.objects.create(number=n, name=f"J{n}")
        except Exception: pass


# ======================================
# Joueurs: parsing & résolution
# ======================================

def _parse_actor_token(text: str):
    s = (text or "").strip(); low = s.lower()
    if not s: return None, None
    if low.startswith("id:"):
        try: return ("id", int(s[3:].strip()))
        except Exception: return (None, None)
    if s.startswith("#"):
        try: return ("number", int(s[1:].strip()))
        except Exception: return (None, None)
    if s.isdigit(): return ("number", int(s))
    return ("name", s)

def _resolve_player_from_kind(kind: str, value, club=None):
    if not kind: return None
    qs = Player.objects.all()
    if club: qs = qs.filter(club=club)

    if kind == "number":
        if value is None: return None
        pl = qs.filter(number=int(value)).first()
        if pl: return pl
        if AUTO_CREATE_PLAYERS and club:
            return Player.objects.create(number=int(value), club=club)
        return None

    if kind == "id":
        if value is None: return None
        pl = qs.filter(pk=int(value)).first()
        if pl: return pl
        if not club: return Player.objects.filter(pk=int(value)).first()
        return Player.objects.filter(pk=int(value), club=club).first()

    if kind == "name":
        parts = str(value).split()
        if len(parts) >= 2:
            first = parts[0]; last = " ".join(parts[1:])
            pl = qs.filter(Q(first_name__iexact=first) & Q(last_name__iexact=last)).first()
            if pl: return pl
        pl = qs.filter(Q(first_name__iexact=str(value)) | Q(last_name__iexact=str(value))).first()
        if pl: return pl
        if AUTO_CREATE_PLAYERS and club:
            first = parts[0]; last = " ".join(parts[1:]) if len(parts) > 1 else ""
            return Player.objects.create(first_name=first, last_name=last, club=club)
        return None

    return None


# ======================================
# Parsing lignes buts & cartons
# ======================================

def _parse_goal_line(line: str):
    raw = (line or "").strip()
    if not raw: return None

    assist_token = None; tags = []
    if "(" in raw and ")" in raw:
        inside = raw[raw.find("(")+1: raw.rfind(")")].strip()
        if inside:
            t = inside.replace(".", "").replace("_", "").lower()
            if t in {"pen","p","pk","penalty","csc","og","owngoal","own goal"}:
                tags.append(t)
            else:
                assist_token = inside
        raw = (raw[:raw.find("(")] + raw[raw.rfind(")")+1:]).strip()

    parts = raw.split(); minute = 0; min_idx = None
    for i, tok in enumerate(parts):
        mm = _extract_minute(tok)
        if mm > 0: minute = mm; min_idx = i; break

    who = " ".join(parts[:min_idx]).strip() if min_idx is not None else " ".join(parts).strip()
    if min_idx is not None and min_idx + 1 < len(parts):
        trailing = [t.strip("[]().,;").lower() for t in parts[min_idx + 1:]]
        tags.extend(trailing)

    tagset = set()
    for t in tags:
        t = t.replace(".", "")
        if t in {"pen","p","pk","penalty"}: tagset.add("pen")
        if t in {"csc","og","owngoal","own"}: tagset.add("og")

    pkind, pval = _parse_actor_token(who)
    akind, aval = (None, None)
    if assist_token: akind, aval = _parse_actor_token(assist_token)

    return {
        "minute": minute,
        "player_kind": pkind, "player_value": pval,
        "assist_kind": akind, "assist_value": aval,
        "is_penalty": "pen" in tagset, "is_own_goal": "og" in tagset,
    }

def _parse_card_line(line: str):
    raw = (line or "").strip()
    if not raw: return None
    parts = raw.split()
    if not parts: return None

    color = None; minute = 0; who_parts = parts[:]
    if len(parts) >= 2:
        maybe_min = _extract_minute(parts[-2]); maybe_col = _normalize_card_color(parts[-1])
        if maybe_min > 0 and maybe_col in {"Y","R"}:
            minute = maybe_min; color = maybe_col; who_parts = parts[:-2]
        else:
            maybe_min2 = _extract_minute(parts[-1])
            if maybe_min2 > 0: minute = maybe_min2; who_parts = parts[:-1]
    if not color: color = "Y"

    who = " ".join(who_parts).strip()
    if not who: return None

    pkind, pval = _parse_actor_token(who)
    return {"minute": minute, "color": color, "player_kind": pkind, "player_value": pval}


# ======================================
# VUES ADMIN (pages HTML)
# ======================================

@staff_member_required
def quick_add_match_view(request):
    _ensure_rounds_seeded(total=26)

    if request.method == "POST":
        home_val = request.POST.get("home_id") or request.POST.get("home") or ""
        away_val = request.POST.get("away_id") or request.POST.get("away") or ""

        home = _resolve_club(home_val)
        away = _resolve_club(away_val)

        if not home or not away:
            messages.error(request, "Sélectionne correctement les deux équipes (picker ou nom).")
            return redirect("admin_quick_match")
        if home.id == away.id:
            messages.error(request, "Les deux équipes ne peuvent pas être identiques.")
            return redirect("admin_quick_match")

        try: home_score = int(request.POST.get("home_score") or 0)
        except Exception: home_score = 0
        try: away_score = int(request.POST.get("away_score") or 0)
        except Exception: away_score = 0
        try: minute = int(request.POST.get("minute") or 0)
        except Exception: minute = 0

        status = _normalize_status(request.POST.get("status"))
        buteur = (request.POST.get("buteur") or "").strip()

        round_id = request.POST.get("round_id") or ""
        rnd = Round.objects.filter(id=round_id).first() if str(round_id).isdigit() else None
        if rnd is None: rnd = Round.objects.order_by("number", "id").first()

        kickoff_raw = (request.POST.get("kickoff_at") or "").strip()
        dt = _parse_dt(kickoff_raw)

        if Match.objects.filter(round=rnd, home_club=home, away_club=away).exists():
            messages.warning(request, "Un match identique existe déjà pour cette journée.")
            return redirect("admin_quick_match")

        Match.objects.create(
            round=rnd, datetime=dt,
            home_club=home, away_club=away,
            home_score=home_score, away_score=away_score,
            status=status, minute=minute, buteur=buteur,
        )
        messages.success(request, "Match ajouté avec succès.")
        return redirect("admin_quick_match")

    matches = (Match.objects.select_related("home_club", "away_club", "round").order_by("-id")[:50])
    ctx = {"STATUSES": ADMIN_STATUSES, "rounds": Round.objects.order_by("number","id"), "matches": matches}
    ctx.update(admin.site.each_context(request))
    return render(request, "admin/matches/quick_add.html", ctx)


@staff_member_required
def quick_events(request):
    if request.method == "POST":
        match_id = request.POST.get("match_id")
        club_val = request.POST.get("club_id") or request.POST.get("club") or ""
        goals_text = request.POST.get("goals_text") or ""
        cards_text = request.POST.get("cards_text") or ""

        match = (Match.objects.select_related("home_club","away_club")
                 .filter(id=_to_int(match_id)).first())
        if not match:
            messages.error(request, "Match introuvable.")
            return redirect("admin_quick_events")

        club = _resolve_club(club_val)
        if not club or (club.id not in {match.home_club_id, match.away_club_id}):
            messages.error(request, "Sélectionne un club du match.")
            return redirect("admin_quick_events")

        created_goals, created_cards = 0, 0
        with transaction.atomic():
            for line in goals_text.splitlines():
                parsed = _parse_goal_line(line)
                if not parsed: continue
                minute = parsed.get("minute", 0)
                scorer = _resolve_player_from_kind(parsed.get("player_kind"), parsed.get("player_value"), club=club)
                if not scorer: continue
                assist_player = None
                ak, av = parsed.get("assist_kind"), parsed.get("assist_value")
                if ak: assist_player = _resolve_player_from_kind(ak, av, club=club)
                is_pen = bool(parsed.get("is_penalty")); is_og = bool(parsed.get("is_own_goal"))

                goal_kwargs = dict(match=match, club=club, minute=minute, player=scorer)
                if assist_player:
                    if _model_has_field(Goal, "assist"): goal_kwargs["assist"] = assist_player
                    elif _model_has_field(Goal, "assist_player"): goal_kwargs["assist_player"] = assist_player
                goal_kwargs = _set_goal_type_kwargs(goal_kwargs, is_pen, is_og, clear_when_false=True)
                goal_kwargs = _ensure_csc_fallback_kwargs(goal_kwargs, is_og)
                Goal.objects.create(**goal_kwargs); created_goals += 1

            for line in cards_text.splitlines():
                parsed = _parse_card_line(line)
                if not parsed: continue
                minute = parsed.get("minute", 0); color = parsed.get("color", "Y")
                pl = _resolve_player_from_kind(parsed.get("player_kind"), parsed.get("player_value"), club=club)
                if not pl: continue
                card_kwargs = dict(match=match, club=club, minute=minute, player=pl)
                card_kwargs = _set_card_color_kwargs(card_kwargs, color)
                Card.objects.create(**card_kwargs); created_cards += 1

        messages.success(request, f"Événements enregistrés: {created_goals} but(s), {created_cards} carton(s).")
        return redirect("admin_quick_events")

    matches = (Match.objects.select_related("home_club","away_club","round").order_by("-id")[:100])
    ctx = {
        "STATUSES": ADMIN_STATUSES,
        "rounds": Round.objects.filter(number__isnull=False).order_by("number","id"),
        "matches": matches, "clubs": Club.objects.order_by("name"),
    }
    ctx.update(admin.site.each_context(request))
    return render(request, "admin/events/quick_events.html", ctx)


# ======================================
# API JSON admin (événements)
# ======================================

def _abs_url(request, url_or_field):
    if not url_or_field: return None
    try: u = url_or_field.url
    except Exception: u = str(url_or_field)
    if not u: return None
    if u.startswith("http"): return u
    return request.build_absolute_uri(u) if request else u

def _serialize_goal(g, request):
    p = getattr(g, "player", None)
    a = getattr(g, "assist", None) or getattr(g, "assist_player", None)
    def _get_bool(obj, *names):
        for n in names:
            if hasattr(obj, n): return bool(getattr(obj, n))
        return False
    return {
        "id": g.id, "minute": g.minute, "club_id": g.club_id,
        "club_name": getattr(g.club, "name", ""),
        "player_id": getattr(p, "id", None),
        "player_name": ((getattr(p,"first_name","")+" "+getattr(p,"last_name","")).strip()
                        or (f"#{p.number}" if getattr(p,"number",None) else "")) if p else "",
        "player_number": getattr(p, "number", None) if p else None,
        "player_photo": _abs_url(request, getattr(p,"photo",None)) if p else None,
        "assist_id": getattr(a,"id",None) if a else None,
        "assist_name": ((getattr(a,"first_name","")+" "+getattr(a,"last_name","")).strip()
                        or (f"#{a.number}" if getattr(a,"number",None) else "")) if a else "",
        "is_penalty": _get_bool(g,"is_penalty","penalty","on_penalty"),
        "is_own_goal": _get_bool(g,"is_own_goal","own_goal","og"),
        "type": getattr(g,"type",None) or getattr(g,"kind",None),
    }

def _serialize_card(c, request):
    p = getattr(c, "player", None)
    color = getattr(c, "color", None) or getattr(c, "card", None) or getattr(c, "type", None) or getattr(c, "card_type", None)
    return {
        "id": c.id, "minute": c.minute, "club_id": c.club_id,
        "club_name": getattr(c.club, "name", ""),
        "color": str(color) if color is not None else None,
        "player_id": getattr(p, "id", None),
        "player_name": ((getattr(p,"first_name","")+" "+getattr(p,"last_name","")).strip()
                        or (f"#{p.number}" if getattr(p,"number",None) else "")) if p else "",
        "player_number": getattr(p, "number", None) if p else None,
        "player_photo": _abs_url(request, getattr(p,"photo",None)) if p else None,
    }

def _json_events(request):
    if request.content_type and "application/json" in request.content_type:
        try: return json.loads(request.body.decode("utf-8"))
        except Exception: return {}
    return request.POST

@staff_member_required
@require_http_methods(["GET", "POST", "DELETE"])
def quick_events_api(request):
    action = request.GET.get("action") or request.POST.get("action")

    if request.method == "GET":
        if action != "list": return HttpResponseBadRequest("action=list attendu")
        match_id = _to_int(request.GET.get("match_id"))
        if not match_id: return HttpResponseBadRequest("match_id manquant")

        goal_sr = ["player","club"]
        if _model_has_field(Goal,"assist"): goal_sr.append("assist")
        if _model_has_field(Goal,"assist_player"): goal_sr.append("assist_player")

        goals = (Goal.objects.select_related(*goal_sr).filter(match_id=match_id).order_by("minute","id"))
        cards = (Card.objects.select_related("player","club").filter(match_id=match_id).order_by("minute","id"))
        return JsonResponse({"goals":[_serialize_goal(g,request) for g in goals],
                             "cards":[_serialize_card(c,request) for c in cards]})

    data = _json_events(request)

    if action == "update_goal":
        g = Goal.objects.select_related("player","club").filter(id=_to_int(data.get("id"))).first()
        if not g: return HttpResponseBadRequest("But introuvable")
        if "minute" in data and str(data["minute"]).strip() != "": g.minute = _to_int(data["minute"], g.minute)
        if data.get("player_token"):
            kind, value = _parse_actor_token(str(data["player_token"]))
            pl = _resolve_player_from_kind(kind, value, club=g.club)
            if pl: g.player = pl
        if "assist_token" in data:
            token = str(data.get("assist_token") or "").strip()
            ap = None
            if token:
                ak, av = _parse_actor_token(token)
                ap = _resolve_player_from_kind(ak, av, club=g.club)
            if _model_has_field(type(g),"assist"): g.assist = ap
            elif _model_has_field(type(g),"assist_player"): g.assist_player = ap
        if "is_penalty" in data or "is_own_goal" in data:
            is_pen = _is_truthy(data.get("is_penalty","0")); is_og = _is_truthy(data.get("is_own_goal","0"))
            kw = {}; _set_goal_type_kwargs(kw, is_pen, is_og, clear_when_false=True)
            for k,v in kw.items(): setattr(g,k,v)
            has_store = any(_model_has_field(Goal,f) for f in ("own_goal","is_own_goal","og","type","kind"))
            if is_og and not has_store and _model_has_field(Goal,"assist_name"):
                if not getattr(g,"assist",None) and not getattr(g,"assist_player",None): g.assist_name = "CSC"
            if (not is_og) and _model_has_field(Goal,"assist_name"):
                if (getattr(g,"assist_name","") or "").upper() == "CSC": g.assist_name = None
        g.save()
        return JsonResponse({"ok": True, "goal": _serialize_goal(g, request)})

    if action == "delete_goal":
        g = Goal.objects.filter(id=_to_int(data.get("id"))).first()
        if not g: return HttpResponseBadRequest("But introuvable")
        g.delete(); return JsonResponse({"ok": True})

    if action == "update_card":
        c = Card.objects.select_related("player","club").filter(id=_to_int(data.get("id"))).first()
        if not c: return HttpResponseBadRequest("Carton introuvable")
        if "minute" in data and str(data["minute"]).strip() != "": c.minute = _to_int(data["minute"], c.minute)
        if data.get("player_token"):
            kind, value = _parse_actor_token(str(data["player_token"]))
            pl = _resolve_player_from_kind(kind, value, club=c.club)
            if pl: c.player = pl
        if data.get("color"):
            kw = {}; _set_card_color_kwargs(kw, str(data["color"]))
            for k,v in kw.items(): setattr(c,k,v)
        c.save(); return JsonResponse({"ok": True, "card": _serialize_card(c, request)})

    if action == "delete_card":
        c = Card.objects.filter(id=_to_int(data.get("id"))).first()
        if not c: return HttpResponseBadRequest("Carton introuvable")
        c.delete(); return JsonResponse({"ok": True})

    if action == "upload_photo":
        pid = _to_int(request.POST.get("player_id")); f = request.FILES.get("photo")
        if not pid or not f: return HttpResponseBadRequest("player_id et photo requis")
        p = Player.objects.filter(id=pid).first()
        if not p: return HttpResponseBadRequest("Joueur introuvable")
        p.photo = f; p.save()
        return JsonResponse({"ok": True, "photo": _abs_url(request, p.photo)})

    return HttpResponseBadRequest("Action inconnue")


# ======================================
# LINEUPS — parsing bloc textarea
# ======================================

def _parse_lineup_block(block: str):
    if not block: return []
    POS = {
        "GK","RB","CB","LB","RWB","LWB",
        "DM","CM","AM","MOC","MC","MG","MD",
        "RW","LW","W","ST","CF","G","DC","DL","DR","M","A"
    }
    rows = []
    for raw in block.splitlines():
        s = (raw or "").strip()
        if not s: continue
        cap = False
        if s.endswith(" (C)") or s.endswith(" (c)") or s.endswith(" C") or s.endswith(" c") or "(C)" in s or "(c)" in s:
            cap = True
            s = (s.replace("(C)","").replace("(c)","")).rstrip().rstrip("C").rstrip("c").rstrip()
        if s and s[0].isdigit():
            head = s[:3]
            if "." in head: s = s.split(".",1)[-1].strip()
            elif ")" in head: s = s.split(")",1)[-1].strip()

        tokens = s.split()
        pkind, pval = None, None
        number = None; position = ""; name_tokens = []

        if tokens and tokens[0].lower().startswith("id:"):
            try: pkind = "id"; pval = int(tokens[0][3:]); tokens = tokens[1:]
            except Exception: pass

        if not pkind and tokens and tokens[0].startswith("#"):
            try:
                number = int(tokens[0][1:])
                pkind, pval = "number", number
                tokens = tokens[1:]
            except Exception: pass

        pos_idx = None
        for i,t in enumerate(tokens):
            if t.upper() in POS: position = t.upper(); pos_idx = i; break

        if pos_idx is not None:
            name_tokens = tokens[:pos_idx]
            rest = tokens[pos_idx+1:]
            if rest and rest[0].isdigit():
                try: number = int(rest[0])
                except Exception: pass
        else:
            name_tokens = tokens

        name = " ".join(name_tokens).strip()
        if not pkind and not name:
            if tokens and tokens[0].isdigit():
                number = int(tokens[0]); pkind, pval = "number", number
        if not pkind and name: pkind, pval = "name", name

        rows.append({
            "player_kind": pkind, "player_value": pval,
            "name": name, "number": number,
            "position": position or "", "is_captain": cap,
        })
    return rows


# ======================================
# LINEUPS — page & API admin rapides
# ======================================

@staff_member_required
def quick_lineups(request):
    if Lineup is None:
        messages.error(request, "Le modèle Lineup n'est pas encore disponible.")
        return redirect("admin:index")

    matches = (Match.objects.select_related("home_club","away_club","round").order_by("-id")[:100])

    if request.method == "POST":
        match_id = _to_int(request.POST.get("match_id"))
        match = Match.objects.filter(id=match_id).select_related("home_club","away_club").first()
        if not match:
            messages.error(request, "Match introuvable.")
            return redirect("admin_quick_lineups")

        replace = _is_truthy(request.POST.get("replace", "1"))

        home_xi    = request.POST.get("home_xi")    or ""
        home_bench = request.POST.get("home_bench") or ""
        away_xi    = request.POST.get("away_xi")    or ""
        away_bench = request.POST.get("away_bench") or ""

        home_form = (request.POST.get("home_formation") or "").strip()
        away_form = (request.POST.get("away_formation") or "").strip()
        home_coach = (request.POST.get("home_coach") or "").strip()
        away_coach = (request.POST.get("away_coach") or "").strip()

        home_rows = _parse_lineup_block(home_xi)
        home_rows_bench = _parse_lineup_block(home_bench)
        away_rows = _parse_lineup_block(away_xi)
        away_rows_bench = _parse_lineup_block(away_bench)

        created = 0
        with transaction.atomic():
            if replace:
                Lineup.objects.filter(match=match).delete()

            def _upsert_side(rows, club, is_starting=True):
                nonlocal created
                order = 0

                def hasf(name: str) -> bool:
                    try:
                        Lineup._meta.get_field(name)
                        return True
                    except Exception:
                        return False

                for r in rows:
                    order += 1
                    pk, pv = r["player_kind"], r["player_value"]
                    player = None
                    if pk == "id" and pv:
                        player = Player.objects.filter(id=pv).first()
                    elif pk == "number" and pv is not None:
                        player = Player.objects.filter(club=club, number=pv).first()
                    elif pk == "name" and r["name"]:
                        name = r["name"]
                        player = Player.objects.filter(club=club, name__iexact=name).first()
                        if not player:
                            parts = name.split()
                            if len(parts) >= 2:
                                player = Player.objects.filter(
                                    club=club,
                                    first_name__iexact=parts[0],
                                    last_name__iexact=" ".join(parts[1:])
                                ).first()

                    kwargs = {"match": match, "club": club}
                    if hasf("player"): kwargs["player"] = player
                    if hasf("player_name") and not player:
                        kwargs["player_name"] = _clamp_field(Lineup, "player_name", r["name"] or "")
                    if hasf("number"):
                        kwargs["number"] = r["number"] or getattr(player, "number", None)
                    if hasf("position"):
                        pos_raw = _normalize_position(r["position"])
                        pos_raw = _clamp_field(Lineup, "position", pos_raw)
                        kwargs["position"] = pos_raw
                    if hasf("is_starting"): kwargs["is_starting"] = bool(is_starting)
                    if hasf("is_captain"):  kwargs["is_captain"] = bool(r["is_captain"])
                    if hasf("rating") and r.get("rating") not in (None, ""):
                        try: kwargs["rating"] = float(str(r["rating"]).replace(",", "."))
                        except Exception: pass
                    if hasf("order"): kwargs["order"] = order
                    elif hasf("sort_order"): kwargs["sort_order"] = order

                    Lineup.objects.create(**kwargs); created += 1

            _upsert_side(home_rows, match.home_club, is_starting=True)
            _upsert_side(home_rows_bench, match.home_club, is_starting=False)
            _upsert_side(away_rows, match.away_club, is_starting=True)
            _upsert_side(away_rows_bench, match.away_club, is_starting=False)

            if TeamInfoPerMatch is not None:
                thi, _ = TeamInfoPerMatch.objects.get_or_create(match=match, club=match.home_club)
                if home_form or home_coach or replace:
                    thi.formation = home_form; thi.coach_name = home_coach; thi.save()
                tai, _ = TeamInfoPerMatch.objects.get_or_create(match=match, club=match.away_club)
                if away_form or away_coach or replace:
                    tai.formation = away_form; tai.coach_name = away_coach; tai.save()

        messages.success(request, f"Compositions enregistrées ({created} lignes).")
        return redirect("admin_quick_lineups")

    ctx = {"matches": matches}
    ctx.update(admin.site.each_context(request))
    return render(request, "admin/lineups/quick_lineups.html", ctx)


@staff_member_required
@require_http_methods(["GET", "POST"])
def quick_lineups_api(request):
    """
    GET  : action=list&match_id=...
           -> renvoie les lineups existants groupés par club/statut + **rating**
    POST : action=set_rating   id=<lineup_id>  rating=<float>
           action=save         id=<lineup_id>  (optionnel: number, position, is_captain, is_starting, rating)
    """
    if Lineup is None:
        return JsonResponse({"detail": "Lineup indisponible"}, status=400)

    # action via GET/POST (form)
    action = request.GET.get("action") or request.POST.get("action") or ""

    # -------- LIST --------
    if request.method == "GET":
        if action != "list":
            return HttpResponseBadRequest("action=list attendu")
        match_id = _to_int(request.GET.get("match_id"))
        m = Match.objects.filter(id=match_id).select_related("home_club", "away_club").first()
        if not m:
            return HttpResponseBadRequest("match_id invalide")

        rows = (
            Lineup.objects
            .filter(match=m)
            .select_related("club", "player")
            .annotate(pos_rank=_position_rank_expr())
            .order_by(
                "club_id",
                "-is_starting",
                "pos_rank",
                "sort_order" if hasattr(Lineup, "sort_order") else "number",
                "number",
                "id",
            )
        )

        def _row(x):
            p = getattr(x, "player", None)
            name = (x.player_name or getattr(p, "name", None) or
                    f"{getattr(p,'first_name','')} {getattr(p,'last_name','')}".strip() or "")
            rv = getattr(x, "rating", None)
            try:
                rv = float(str(rv).replace(",", ".")) if rv not in (None, "") else None
            except Exception:
                rv = None
            return {
                "id": x.id,
                "club_id": x.club_id,
                "is_starting": bool(x.is_starting),
                "number": x.number,
                "position": x.position,
                "name": name.strip(),
                "is_captain": bool(x.is_captain),
                "rating": rv,
            }

        out = {"home": {"club_id": m.home_club_id, "xi": [], "bench": []},
               "away": {"club_id": m.away_club_id, "xi": [], "bench": []}}
        for r in rows:
            side = "home" if r.club_id == m.home_club_id else "away"
            (out[side]["xi"] if r.is_starting else out[side]["bench"]).append(_row(r))
        return JsonResponse(out)

    # -------- WRITE --------
    data = {}
    if request.content_type and "application/json" in (request.content_type or ""):
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            data = {}
    if not data:
        data = request.POST

    # ⚠️ IMPORTANT : si 'action' n'était pas dans GET/POST, lis-la depuis le JSON
    if not action:
        action = str(data.get("action") or "").strip()

    # a) set_rating (léger et pratique pour l'AJAX)
    if action == "set_rating":
        lid = _to_int(data.get("id"))
        if not lid:
            return HttpResponseBadRequest("id manquant")
        li = Lineup.objects.filter(id=lid).first()
        if not li:
            return HttpResponseBadRequest("Lineup introuvable")
        val = data.get("rating", None)
        if val in (None, "", "null"):
            li.rating = None
        else:
            try:
                li.rating = float(str(val).replace(",", "."))
            except Exception:
                return HttpResponseBadRequest("rating invalide")
        li.save(update_fields=["rating"])
        return JsonResponse({"ok": True, "id": li.id, "rating": li.rating})

    # b) save : petite mise à jour générique (si id fourni)
    if action == "save":
        lid = _to_int(data.get("id"))
        if not lid:
            return HttpResponseBadRequest("id manquant")
        li = Lineup.objects.filter(id=lid).first()
        if not li:
            return HttpResponseBadRequest("Lineup introuvable")

        up_fields = []
        if "number" in data and str(data["number"]).strip() != "":
            li.number = _to_int(data["number"], li.number); up_fields.append("number")
        if "position" in data:
            pos = _normalize_position(str(data["position"]))
            li.position = _clamp_field(Lineup, "position", pos)
            up_fields.append("position")
        if "is_captain" in data:
            li.is_captain = _is_truthy(data["is_captain"]); up_fields.append("is_captain")
        if "is_starting" in data:
            li.is_starting = _is_truthy(data["is_starting"]); up_fields.append("is_starting")
        if "rating" in data:
            val = data.get("rating")
            if val in (None, "", "null"):
                li.rating = None
            else:
                try:
                    li.rating = float(str(val).replace(",", "."))
                except Exception:
                    return HttpResponseBadRequest("rating invalide")
            up_fields.append("rating")

        if up_fields:
            li.save(update_fields=up_fields)
        return JsonResponse({"ok": True, "id": li.id})

    return HttpResponseBadRequest("Action inconnue")
