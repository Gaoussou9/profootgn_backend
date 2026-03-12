from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone

from .models import Competition, CompetitionTeam, CompetitionMatch


@staff_member_required
def competition_matches_view(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    # =========================
    # ÉQUIPES DE LA COMPÉTITION
    # =========================
    teams = CompetitionTeam.objects.filter(
        competition=competition,
        is_active=True
    ).order_by("name")

    team_count = teams.count()

    # =========================
    # JOURNÉES (ALLER / RETOUR)
    # =========================
    matchdays = []
    if team_count >= 2:
        total_matchdays = 2 * (team_count - 1)
        matchdays = list(range(1, total_matchdays + 1))

    # =========================
    # MATCHS
    # =========================
    matches = CompetitionMatch.objects.filter(
        competition=competition
    ).select_related(
        "home_team",
        "away_team"
    ).order_by("-matchday", "-datetime")

    # =========================
    # ACTIONS POST
    # =========================
    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        # ➕ AJOUT MATCH
        if action == "add_match":
            CompetitionMatch.objects.create(
                competition=competition,
                matchday=int(request.POST.get("matchday")),
                home_team_id=request.POST.get("home_team"),
                away_team_id=request.POST.get("away_team"),
                datetime=request.POST.get("datetime"),
                status="SCHEDULED",
            )
            return redirect(request.path)

        # 🔄 ACTIONS SUR MATCH EXISTANT
        match_id = request.POST.get("match_id")
        if match_id:
            match = get_object_or_404(
                CompetitionMatch,
                id=match_id,
                competition=competition
            )

            now = timezone.now()

            # =====================
            # CHRONO / STATUTS
            # =====================

            # ▶️ DÉMARRER
            if action == "start":
                if match.status in ["SCHEDULED", "HT"]:
                    match.phase_offset = 0
                    match.phase_start = now
                    match.status = "LIVE"

            # ⏸️ PAUSE (MI-TEMPS)
            elif action == "pause":
                if match.status == "LIVE":
                    # forcer minute 45
                    match.phase_offset = 45 * 60
                    match.phase_start = None
                    match.status = "HT"

            # ▶️ REPRENDRE
            elif action == "resume":
                if match.status == "HT":
                    match.phase_offset = 45 * 60
                    match.phase_start = now
                    match.status = "LIVE"

            # ⏹️ FIN DU MATCH
            elif action == "finish":
                    match.phase_start = None
                    match.status = "FT"

            # 📅 PROGRAMMÉ
            elif action == "scheduled":
                match.phase_start = None
                match.phase_offset = 0
                match.status = "SCHEDULED"

            # 🔁 REPORTÉ
            elif action == "postponed":
                match.phase_start = None
                match.status = "POSTPONED"

            # 🚫 ANNULÉ
            elif action == "cancelled":
                match.phase_start = None
                match.status = "CANCELLED"

            # =====================
            # MODIFICATION SCORE
            # =====================
            elif action == "update_score":
                try:
                    match.home_score = int(
                        request.POST.get("home_score", match.home_score)
                    )
                    match.away_score = int(
                        request.POST.get("away_score", match.away_score)
                    )
                except ValueError:
                    pass

            # =====================
            # SUPPRESSION
            # =====================
            elif action == "delete":
                match.delete()
                return redirect(request.path)

            match.save()
            return redirect(request.path)

    # =========================
    # CONTEXTE
    # =========================
    context = {
        "competition": competition,
        "teams": teams,
        "matches": matches,
        "matchdays": matchdays,
        "team_count": team_count,
    }

    return render(
        request,
        "admin/competitions/competition_matches.html",
        context
    )
