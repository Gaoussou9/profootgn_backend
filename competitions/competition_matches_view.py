from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required

from .models import Competition, CompetitionTeam, CompetitionMatch


@staff_member_required
def competition_matches_view(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    # Équipes de la compétition
    teams = CompetitionTeam.objects.filter(
        competition=competition,
        is_active=True
    ).order_by("name")

    # Matchs existants
    matches = CompetitionMatch.objects.filter(
        competition=competition
    ).select_related(
        "home_team",
        "away_team"
    ).order_by("-datetime")

    # =========================
    # JOURNÉES (1 → 38 par défaut)
    # =========================
    MAX_MATCHDAYS = 38
    matchdays = list(range(1, MAX_MATCHDAYS + 1))

    # ➕ Ajouter un match
    if request.method == "POST" and request.POST.get("action") == "add_match":
        CompetitionMatch.objects.create(
            competition=competition,
            matchday=int(request.POST.get("matchday")),
            home_team_id=request.POST.get("home_team"),
            away_team_id=request.POST.get("away_team"),
            datetime=request.POST.get("datetime"),
        )
        return redirect(request.path)

    context = {
        "competition": competition,
        "teams": teams,
        "matches": matches,
        "matchdays": matchdays,  # ✅ OBLIGATOIRE
    }

    return render(
        request,
        "admin/competitions/competition_matches.html",
        context
    )
