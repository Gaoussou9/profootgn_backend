from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.dateparse import parse_datetime

from .models import Competition, CompetitionTeam
from matches.models import Match, Round
from clubs.models import Club


@staff_member_required
def competition_matches_view(request, competition_id):
    # =====================================================
    # 🔒 SOURCE DE VÉRITÉ : compétition courante
    # =====================================================
    competition = get_object_or_404(Competition, id=competition_id)

    # =====================================================
    # JOURNÉES STRICTEMENT LIÉES À LA COMPÉTITION
    # =====================================================
    rounds = Round.objects.filter(
        competition=competition
    ).order_by("number")

    # =====================================================
    # CLUBS ENGAGÉS DANS LA COMPÉTITION (SOURCE UNIQUE)
    # =====================================================
    clubs = Club.objects.filter(
        club_competitions__competition=competition,
        club_competitions__is_active=True
    ).distinct().order_by("name")

    # =====================================================
    # MATCHS STRICTEMENT DE LA COMPÉTITION
    # =====================================================
    matches = Match.objects.filter(
        round__competition=competition
    ).select_related(
        "round", "home_club", "away_club"
    ).order_by("-datetime")

    # =====================================================
    # ➕ AJOUT D’UN MATCH (SÉCURISÉ À 100 %)
    # =====================================================
    if request.method == "POST" and request.POST.get("action") == "add_match":
        round_id = request.POST.get("round")
        home_id = request.POST.get("home_club")
        away_id = request.POST.get("away_club")
        datetime_str = request.POST.get("datetime")

        # Sécurité basique
        if not all([round_id, home_id, away_id, datetime_str]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect(request.path)

        if home_id == away_id:
            messages.error(request, "Une équipe ne peut pas jouer contre elle-même.")
            return redirect(request.path)

        # 🔐 La journée DOIT appartenir à la compétition
        round_obj = Round.objects.filter(
            id=round_id,
            competition=competition
        ).first()

        if not round_obj:
            messages.error(request, "Journée invalide pour cette compétition.")
            return redirect(request.path)

        # 🔐 Les clubs DOIVENT être engagés dans la compétition
        valid_clubs = CompetitionClub.objects.filter(
            competition=competition,
            is_active=True,
            club_id__in=[home_id, away_id]
        ).values_list("club_id", flat=True)

        if len(valid_clubs) != 2:
            messages.error(
                request,
                "Les clubs sélectionnés ne sont pas engagés dans cette compétition."
            )
            return redirect(request.path)

        # Parsing date sécurisé
        match_datetime = parse_datetime(datetime_str)
        if not match_datetime:
            messages.error(request, "Date et heure invalides.")
            return redirect(request.path)

        # ✅ CRÉATION DU MATCH
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
    # ⚡ ACTIONS RAPIDES (LIVE / HT / FT / etc.)
    # =====================================================
    if request.method == "POST" and request.POST.get("action") == "update_status":
        match_id = request.POST.get("match_id")
        new_status = request.POST.get("status")

        updated = Match.objects.filter(
            id=match_id,
            round__competition=competition
        ).update(status=new_status)

        if updated:
            messages.success(request, "Statut du match mis à jour.")
        else:
            messages.error(request, "Action non autorisée sur ce match.")

        return redirect(request.path)

    # =====================================================
    # CONTEXTE TEMPLATE
    # =====================================================
    context = {
        "competition": competition,
        "rounds": rounds,
        "clubs": clubs,       # ✅ clubs filtrés par CompetitionClub
        "matches": matches,
    }

    return render(
        request,
        "admin/competitions/competition_matches.html",
        context
    )

 # =====================================================
    # CLUBS + JOUEURS
    # =====================================================
def admin_competition_clubs(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    clubs = (
        CompetitionTeam.objects
        .filter(competition=competition, is_active=True)
        .select_related("club")
    )

    # ➕ ajout joueur
    if request.method == "POST" and request.POST.get("action") == "add_player":
        club_id = request.POST.get("club_id")
        Player.objects.create(
            club_id=club_id,
            first_name=request.POST.get("first_name"),
            last_name=request.POST.get("last_name"),
            number=request.POST.get("number") or None,
            position=request.POST.get("position", ""),
        )
        return redirect(request.path)

    return render(
        request,
        "admin/competition_clubs.html",
        {
            "competition": competition,
            "clubs": clubs,
        },
    )
