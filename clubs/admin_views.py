# clubs/admin_views.py

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.utils import ProgrammingError, OperationalError
from django.core.exceptions import ValidationError

from .models import Club, StaffMember
from players.models import Player


@staff_member_required
def quick_clubs(request):
    q = request.GET.get('q', '')
    qs = Club.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by('name')
    return render(request, 'admin_quick/quick_clubs.html', {'clubs': qs, 'q': q})


def _first_staff_role_code():
    try:
        return StaffMember.ROLES[0][0]
    except Exception:
        return "COACH"


def _normalize_staff_role(code):
    """
    S'assure que 'code' est bien un code présent dans StaffMember.ROLES.
    Si absent/incorrect -> renvoie le premier code dispo.
    """
    valid_codes = {c for c, _ in getattr(StaffMember, "ROLES", [])}
    if not valid_codes:
        return code or "COACH"
    return code if code in valid_codes else _first_staff_role_code()


@staff_member_required
def quick_roster(request, club_id):
    """
    GET  -> affiche l'effectif (joueurs + staff) + formulaires d’ajout/édition inline
    POST -> add_player / edit_player / toggle_player_active / delete_player
         -> add_staff  / edit_staff  / toggle_staff_active  / delete_staff
    Résilient si la table Staff n’existe pas encore.
    """
    club = get_object_or_404(Club, pk=club_id)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        # ============ JOUEURS ============
        if action == "add_player":
            first_name = (request.POST.get("first_name") or "").strip()
            last_name  = (request.POST.get("last_name") or "").strip()
            position   = (request.POST.get("position") or "").strip()
            number_raw = request.POST.get("number") or ""
            photo      = request.FILES.get("photo")

            if not first_name and not last_name:
                messages.error(request, "Renseigne au moins le prénom ou le nom du joueur.")
                return redirect("quick_roster", club_id=club.id)

            player = Player(club=club, first_name=first_name, last_name=last_name)
            if hasattr(player, "position"): player.position = position
            if hasattr(player, "number"):
                try:
                    player.number = int(number_raw) if number_raw != "" else None
                except Exception:
                    player.number = None
            if photo and hasattr(player, "photo"): player.photo = photo
            player.save()

            display_name = (first_name + " " + last_name).strip()
            messages.success(request, f"Joueur « {display_name} » ajouté à {club.name}.")
            return redirect("quick_roster", club_id=club.id)

        if action == "edit_player":
            player_id  = request.POST.get("player_id")
            player = get_object_or_404(Player, pk=player_id, club=club)

            player.first_name = (request.POST.get("first_name") or "").strip()
            player.last_name  = (request.POST.get("last_name") or "").strip()
            if hasattr(player, "position"): player.position = (request.POST.get("position") or "").strip()

            if hasattr(player, "number"):
                number_raw = request.POST.get("number")
                try:
                    player.number = int(number_raw) if (number_raw not in (None, "",)) else None
                except Exception:
                    player.number = None

            new_photo = request.FILES.get("photo")
            if new_photo and hasattr(player, "photo"):
                player.photo = new_photo

            player.save()
            messages.success(request, f"Joueur « {player.first_name} {player.last_name} » modifié.")
            return redirect("quick_roster", club_id=club.id)

        if action == "toggle_player_active":
            player_id = request.POST.get("player_id")
            player = get_object_or_404(Player, pk=player_id, club=club)
            if hasattr(player, "is_active"):
                player.is_active = not bool(player.is_active)
                player.save()
                state = "activé" if player.is_active else "désactivé"
                messages.success(request, f"Joueur « {player.first_name} {player.last_name} » {state}.")
            else:
                messages.error(request, "Ce modèle Player n’a pas de champ is_active.")
            return redirect("quick_roster", club_id=club.id)

        if action == "delete_player":
            player_id = request.POST.get("player_id")
            player = get_object_or_404(Player, pk=player_id, club=club)
            name = f"{player.first_name} {player.last_name}".strip() or f"#{player.id}"
            try:
                player.delete()
                messages.success(request, f"Joueur « {name} » supprimé.")
            except Exception as e:
                messages.error(request, f"Suppression impossible : {e}")
            return redirect("quick_roster", club_id=club.id)

        # ============ STAFF ============
        if action == "add_staff":
            staff_name = (request.POST.get("full_name") or "").strip()
            role_code  = _normalize_staff_role(request.POST.get("role"))
            phone      = (request.POST.get("phone") or "").strip()
            email      = (request.POST.get("email") or "").strip()
            photo      = request.FILES.get("photo")

            if not staff_name:
                messages.error(request, "Le nom du membre du staff est requis.")
                return redirect("quick_roster", club_id=club.id)
            try:
                staff = StaffMember(club=club, full_name=staff_name, role=role_code)
                if hasattr(staff, "phone"): staff.phone = phone
                if hasattr(staff, "email"): staff.email = email
                if photo and hasattr(staff, "photo"): staff.photo = photo
                staff.full_clean()
                staff.save()
                messages.success(request, f"Membre du staff « {staff.full_name} » ajouté à {club.name}.")
            except (ProgrammingError, OperationalError):
                messages.error(request, "La table Staff n’existe pas encore. On l’ajoutera à l’étape suivante.")
            except ValidationError as ve:
                messages.error(request, f"Rôle invalide pour le staff (choisis une valeur de la liste).")
            return redirect("quick_roster", club_id=club.id)

        if action == "edit_staff":
            staff_id = request.POST.get("staff_id")
            try:
                staff = StaffMember.objects.get(pk=staff_id, club=club)
            except (ProgrammingError, OperationalError):
                messages.error(request, "La table Staff n’existe pas encore.")
                return redirect("quick_roster", club_id=club.id)

            staff.full_name = (request.POST.get("full_name") or "").strip()
            staff.role      = _normalize_staff_role(request.POST.get("role"))
            if hasattr(staff, "phone"): staff.phone = (request.POST.get("phone") or "").strip()
            if hasattr(staff, "email"): staff.email = (request.POST.get("email") or "").strip()
            new_photo = request.FILES.get("photo")
            if new_photo and hasattr(staff, "photo"): staff.photo = new_photo
            try:
                staff.full_clean()
                staff.save()
                messages.success(request, f"Staff « {staff.full_name} » modifié.")
            except ValidationError:
                messages.error(request, "Rôle invalide pour le staff.")
            return redirect("quick_roster", club_id=club.id)

        if action == "toggle_staff_active":
            staff_id = request.POST.get("staff_id")
            try:
                staff = StaffMember.objects.get(pk=staff_id, club=club)
            except (ProgrammingError, OperationalError):
                messages.error(request, "La table Staff n’existe pas encore.")
                return redirect("quick_roster", club_id=club.id)

            if hasattr(staff, "is_active"):
                staff.is_active = not bool(staff.is_active)
                staff.save()
                state = "activé" if staff.is_active else "désactivé"
                messages.success(request, f"Staff « {staff.full_name} » {state}.")
            else:
                messages.error(request, "is_active n’est pas disponible sur StaffMember.")
            return redirect("quick_roster", club_id=club.id)

        if action == "delete_staff":
            staff_id = request.POST.get("staff_id")
            try:
                staff = StaffMember.objects.get(pk=staff_id, club=club)
            except (ProgrammingError, OperationalError):
                messages.error(request, "La table Staff n’existe pas encore.")
                return redirect("quick_roster", club_id=club.id)

            name = staff.full_name or f"#{staff.id}"
            try:
                staff.delete()
                messages.success(request, f"Membre du staff « {name} » supprimé.")
            except Exception as e:
                messages.error(request, f"Suppression impossible : {e}")
            return redirect("quick_roster", club_id=club.id)

        messages.error(request, "Action inconnue.")
        return redirect("quick_roster", club_id=club.id)

    # ===== GET =====
    players = list(Player.objects.filter(club=club).order_by('last_name', 'first_name'))
    for p in players:
        has_active = hasattr(p, "is_active")
        setattr(p, "has_is_active", has_active)
        setattr(p, "active_state", bool(getattr(p, "is_active", True)) if has_active else True)

    staff_enabled = True
    staff = []
    staff_roles = []
    try:
        staff = list(StaffMember.objects.filter(club=club).order_by('role', 'full_name'))
        for s in staff:
            setattr(s, "active_state", bool(getattr(s, "is_active", True)))
        staff_roles = list(getattr(StaffMember, "ROLES", []))
    except (ProgrammingError, OperationalError):
        staff_enabled = False

    return render(request, 'admin_quick/quick_roster.html', {
        'club': club,
        'players': players,
        'staff': staff,
        'staff_enabled': staff_enabled,
        'staff_roles': staff_roles,
    })


@staff_member_required
def quick_clubs_api(request):
    """Endpoint JSON admin (pickers clubs) : [{id, name, logo}]"""
    q = request.GET.get("q", "").strip()
    qs = Club.objects.only("id", "name", "logo").order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)

    data = []
    for c in qs:
        logo = c.logo.url if c.logo else ""
        if logo:
            logo = request.build_absolute_uri(logo)
        data.append({"id": c.id, "name": c.name, "logo": logo})

    resp = JsonResponse(data, safe=False)
    resp["Cache-Control"] = "private, max-age=60"
    return resp
