from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from django.http import HttpResponse
from django.db import IntegrityError

from .models import Competition, CompetitionTeam, Player
from matches.models import Match, Round


# =====================================================
# MATCHS ADMIN (PAGE PRINCIPALE COMPÉTITION)
# =====================================================

from django.utils import timezone

@staff_member_required
def competition_matches_view(request, competition_id):

    competition = get_object_or_404(Competition, id=competition_id)

    rounds = Round.objects.filter(
        competition=competition
    ).order_by("number")

    teams = (
        CompetitionTeam.objects
        .filter(competition=competition, is_active=True)
        .order_by("name")
    )

    matches = (
        Match.objects
        .filter(round__competition=competition)
        .select_related("round", "home_club", "away_club")
        .order_by("-datetime")
    )

    if request.method == "POST":

        action = request.POST.get("action")
        match_id = request.POST.get("match_id")

        # =====================================================
        # AJOUT MATCH
        # =====================================================

        if action == "add_match":

            round_id = request.POST.get("round")
            home_id = request.POST.get("home_club")
            away_id = request.POST.get("away_club")
            datetime_str = request.POST.get("datetime")

            if not all([round_id, home_id, away_id, datetime_str]):
                messages.error(request, "Tous les champs sont obligatoires.")
                return redirect(request.path)

            if home_id == away_id:
                messages.error(request, "Une équipe ne peut pas jouer contre elle-même.")
                return redirect(request.path)

            round_obj = Round.objects.filter(
                id=round_id,
                competition=competition
            ).first()

            if not round_obj:
                messages.error(request, "Journée invalide.")
                return redirect(request.path)

            match_datetime = parse_datetime(datetime_str)
            if not match_datetime:
                messages.error(request, "Date invalide.")
                return redirect(request.path)

            Match.objects.create(
                round=round_obj,
                home_club_id=home_id,
                away_club_id=away_id,
                datetime=match_datetime,
                status="SCHEDULED",
            )

            messages.success(request, "Match ajouté avec succès.")
            return redirect(request.path)

        # =====================================================
        # ACTIONS SUR MATCH EXISTANT
        # =====================================================

        if match_id:

            match = get_object_or_404(Match, id=match_id)
            now = timezone.now()

            # ▶ DÉMARRER (1ère MT)
            if action == "start":

                match.elapsed_seconds = 0
                match.started_at = now
                match.status = "LIVE"

            # ⏸ PAUSE (FIN 1ère MT EXACT 45:00)
            elif action == "pause":

                if match.status == "LIVE":

                    # 🔥 On force la fin de 1ère mi-temps à 45:00
                    match.elapsed_seconds = 45 * 60
                    match.started_at = None
                    match.status = "HT"

                    match.save()
                    messages.success(request, "Mi-temps atteinte (45').")
                    return redirect(request.path)

            # ▶ REPRENDRE 2E MI-TEMPS (REPART TOUJOURS À 45:00)
            elif action == "resume":

                if match.status == "HT":

                    # 🔥 RESET PROPRE 2e MT
                    match.elapsed_seconds = 45 * 60
                    match.started_at = now
                    match.status = "LIVE"

                    match.save()
                    messages.success(request, "2e mi-temps démarrée à 45'.")
                    return redirect(request.path)

            # 🔥 SYNCHRONISER MINUTE (RETARD)
            elif action == "set_minute":

                try:
                    minute = int(request.POST.get("minute", 0))
                except ValueError:
                    messages.error(request, "Minute invalide.")
                    return redirect(request.path)

                if minute < 0 or minute > 130:
                    messages.error(request, "Minute hors limite (0 - 130).")
                    return redirect(request.path)

                match.elapsed_seconds = minute * 60
                match.started_at = now
                match.status = "LIVE"

                messages.success(request, f"Minute synchronisée à {minute}'.")
                match.save()
                return redirect(request.path)

            # ⏹ FIN MATCH
            elif action == "finish":

                if match.status == "LIVE" and match.started_at:
                    elapsed = int((now - match.started_at).total_seconds())
                    match.elapsed_seconds += elapsed

                match.started_at = None
                match.status = "FT"

            # 🔁 REVENIR À PRÉVU
            elif action == "scheduled":

                match.status = "SCHEDULED"
                match.started_at = None
                match.elapsed_seconds = 0

            match.save()
            return redirect(request.path)

    return render(
        request,
        "admin/competitions/competition_matches.html",
        {
            "competition": competition,
            "rounds": rounds,
            "teams": teams,
            "matches": matches,
        },
    )
# =====================================================
# PAGE CLUBS ADMIN
# =====================================================

@staff_member_required
def admin_competition_clubs(request, competition_id):

    competition = get_object_or_404(Competition, id=competition_id)

    # ✅ Correction ici aussi
    teams = (
        CompetitionTeam.objects
        .filter(competition=competition, is_active=True)
        .order_by("name")
    )

    return render(
        request,
        "admin/competitions/competition_clubs.html",
        {
            "competition": competition,
            "teams": teams,
        },
    )


# =====================================================
# EFFECTIF D'UN CLUB
# =====================================================

@staff_member_required
def competition_club_players_view(request, competition_id, club_id):

    competition = get_object_or_404(Competition, id=competition_id)

    club = get_object_or_404(
        CompetitionTeam,
        id=club_id,
        competition=competition,
        is_active=True
    )

    players = Player.objects.filter(
        club=club,
        is_active=True
    ).order_by("number")

    # =====================================================
    # AJOUT JOUEUR
    # =====================================================

    if request.method == "POST" and request.POST.get("action") == "add_player":

        name = request.POST.get("name")
        number = request.POST.get("number")
        position = request.POST.get("position")
        height = request.POST.get("height")

        if not name or not number or not position:
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
            return redirect(request.path)

        try:
            number = int(number)
        except ValueError:
            messages.error(request, "Le numéro doit être un nombre valide.")
            return redirect(request.path)

        if height:
            try:
                height = int(height)
            except ValueError:
                messages.error(request, "La taille doit être un nombre valide.")
                return redirect(request.path)
        else:
            height = None

        if Player.objects.filter(club=club, number=number, is_active=True).exists():
            messages.error(request, f"Le numéro {number} est déjà utilisé.")
            return redirect(request.path)

        Player.objects.create(
            club=club,
            name=name,
            number=number,
            position=position,
            photo=request.FILES.get("photo"),
            age=request.POST.get("age") or None,
            nationality=request.POST.get("nationality") or "",
            height=height,
            previous_club_1=request.POST.get("previous_club_1") or "",
            previous_club_2=request.POST.get("previous_club_2") or "",
            previous_club_3=request.POST.get("previous_club_3") or "",
        )

        messages.success(request, "Joueur ajouté avec succès.")
        return redirect(request.path)

    # =====================================================
    # UPDATE JOUEUR
    # =====================================================

    if request.method == "POST" and request.POST.get("action") == "update_player":

        player_id = request.POST.get("player_id")

        player = get_object_or_404(
            Player,
            id=player_id,
            club=club,
            is_active=True
        )

        new_number = request.POST.get("number")
        height = request.POST.get("height")

        try:
            new_number = int(new_number)
        except ValueError:
            messages.error(request, "Numéro invalide.")
            return redirect(request.path)

        if height:
            try:
                height = int(height)
            except ValueError:
                messages.error(request, "Taille invalide.")
                return redirect(request.path)
        else:
            height = None

        if Player.objects.filter(
            club=club,
            number=new_number,
            is_active=True
        ).exclude(id=player.id).exists():
            messages.error(request, f"Le numéro {new_number} est déjà utilisé.")
            return redirect(request.path)

        player.name = request.POST.get("name")
        player.number = new_number
        player.position = request.POST.get("position")
        player.age = request.POST.get("age") or None
        player.nationality = request.POST.get("nationality") or ""
        player.height = height
        player.previous_club_1 = request.POST.get("previous_club_1") or ""
        player.previous_club_2 = request.POST.get("previous_club_2") or ""
        player.previous_club_3 = request.POST.get("previous_club_3") or ""

        if request.FILES.get("photo"):
            player.photo = request.FILES.get("photo")

        player.save()

        messages.success(request, "Joueur modifié avec succès.")
        return redirect(request.path)

    # =====================================================
    # SUPPRESSION JOUEUR
    # =====================================================

    if request.method == "POST" and request.POST.get("action") == "delete_player":

        player_id = request.POST.get("player_id")

        player = get_object_or_404(
            Player,
            id=player_id,
            club=club,
            is_active=True
        )

        player.is_active = False
        player.save()

        return HttpResponse(status=200)

    # =====================================================
    # MODE EDITION
    # =====================================================

    edit_player = None
    edit_id = request.GET.get("edit")

    if edit_id:
        edit_player = get_object_or_404(
            Player,
            id=edit_id,
            club=club,
            is_active=True
        )

    return render(
        request,
        "admin/competitions/competition_club_players.html",
        {
            "competition": competition,
            "club": club,
            "players": players,
            "edit_player": edit_player,
        },
    )