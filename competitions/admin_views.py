from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from django.http import HttpResponse
from django.db import IntegrityError

from .models import Competition, CompetitionTeam, Player
from competitions.models import CompetitionMatch as Match
from matches.models import Round

from competitions.models import Goal, Card
from competitions.models import Competition
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
        .filter(competition=competition)
        .select_related("round", "home_team", "away_team")
        .order_by("-datetime")
    )

    if request.method == "POST":

        action = request.POST.get("action")
        match_id = request.POST.get("match_id")

        # ===============================
        # AJOUT MATCH
        # ===============================

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
                home_team_id=home_id,
                away_team_id=away_id,
                datetime=match_datetime,
                status="SCHEDULED",
            )

            messages.success(request, "Match ajouté avec succès.")
            return redirect(request.path)

        # ===============================
        # ACTIONS SUR MATCH
        # ===============================

        if match_id:

            match = get_object_or_404(Match, id=match_id)
            now = timezone.now()

            if action == "start":

                match.phase_offset = 0
                match.phase_start = now
                match.status = "LIVE"

            elif action == "pause":

                if match.status == "LIVE":

                    match.phase_offset = 45 * 60
                    match.phase_start = None
                    match.status = "HT"

                    match.save()
                    messages.success(request, "Mi-temps atteinte (45').")
                    return redirect(request.path)

                    

            elif action == "resume":

                if match.status == "HT":

                    match.phase_offset = 45 * 60
                    match.phase_start = now
                    match.status = "LIVE"

                    match.save()
                    messages.success(request, "2e mi-temps démarrée à 45'.")
                    return redirect(request.path)


            elif action == "set_minute":

                try:
                    minute = int(request.POST.get("minute", 0))
                except ValueError:
                    messages.error(request, "Minute invalide.")
                    return redirect(request.path)

                if minute < 0 or minute > 130:
                    messages.error(request, "Minute hors limite.")
                    return redirect(request.path)

                match.phase_offset = minute * 60
                match.phase_start = now
                match.status = "LIVE"

                match.save()
                messages.success(request, f"Minute synchronisée à {minute}'.")
                return redirect(request.path)

            elif action == "finish":

                match.phase_start = None
                match.status = "FT"

            elif action == "scheduled":

                match.status = "SCHEDULED"
                match.phase_start = None
                match.phase_offset = 0

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

             # 📊 STATISTIQUES
    matches_played=request.POST.get("matches_played") or 0,
    goals=request.POST.get("goals") or 0,
    assists=request.POST.get("assists") or 0,
    yellow_cards=request.POST.get("yellow_cards") or 0,
    red_cards=request.POST.get("red_cards") or 0,
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

        player.matches_played = request.POST.get("matches_played") or 0
        player.goals = request.POST.get("goals") or 0
        player.assists = request.POST.get("assists") or 0
        player.yellow_cards = request.POST.get("yellow_cards") or 0
        player.red_cards = request.POST.get("red_cards") or 0

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
@staff_member_required
def admin_quick_events_view(request, competition_id):

    competition = get_object_or_404(Competition, id=competition_id)

    selected_match_id = request.GET.get("match") or request.POST.get("match_id")
    selected_match = None

    if selected_match_id:
        selected_match = get_object_or_404(
            Match,
            id=selected_match_id,
            competition=competition
        )

    matches = Match.objects.filter(
        competition=competition
    ).select_related("home_team", "away_team").order_by("-id")

    players = []
    if selected_match:
        players = Player.objects.filter(
            club__in=[selected_match.home_team, selected_match.away_team],
            is_active=True
        )

    # ======================
    # POST
    # ======================
    if request.method == "POST":

        match_id = request.POST.get("match_id")

        if not match_id:
            return redirect(request.path)

        match = get_object_or_404(Match, id=match_id)

        # ======================
        # ACTIONS TABLEAU
        # ======================

        if request.POST.get("delete_goal_id"):
            Goal.objects.filter(id=request.POST["delete_goal_id"]).delete()
            return redirect(f"{request.path}?match={match.id}")

        if request.POST.get("delete_card_id"):
            Card.objects.filter(id=request.POST["delete_card_id"]).delete()
            return redirect(f"{request.path}?match={match.id}")

        if request.POST.get("update_goal_id"):
            goal = get_object_or_404(Goal, id=request.POST["update_goal_id"])

            goal.minute = request.POST.get("minute")
            goal.player_id = request.POST.get("player_id")

            assist_player_id = request.POST.get("assist_player_id")
            if assist_player_id:
                try:
                    goal.assist_player = Player.objects.get(id=int(assist_player_id))
                except:
                    goal.assist_player = None
            else:
                goal.assist_player = None

            goal.type = request.POST.get("goal_type", "normal")
            goal.save()

            return redirect(f"{request.path}?match={match.id}")

        if request.POST.get("update_card_id"):
            card = get_object_or_404(Card, id=request.POST["update_card_id"])

            minute = request.POST.get("minute")
            player_id = request.POST.get("player_id")
            color = request.POST.get("color")

            try:
                if minute:
                    card.minute = int(minute)
            except:
                pass

            if player_id:
                try:
                    player = Player.objects.get(id=int(player_id))
                    card.player = player
                    card.club = player.club
                except:
                    pass

            if color in ["yellow", "red"]:
                card.color = color

            card.reason = request.POST.get("card_reason", "foul")

            card.save()
            return redirect(f"{request.path}?match={match.id}")

        # ======================
        # AJOUT EVENTS
        # ======================

        goals_text = request.POST.get("goals", "")
        cards_text = request.POST.get("cards", "")

        # ---------- GOALS (🔥 CORRIGÉ) ----------
        for line in goals_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Exemple attendu :
            # Abdoulaye (Ferran) 12 [penalty]
            # Abdoulaye 45 [freekick]
            # Abdoulaye 90 [own_goal]

            parts = line.split()
            if len(parts) < 2:
                continue

            # 🔥 TYPE
            goal_type = "normal"
            if "[" in line and "]" in line:
                goal_type = line.split("[")[-1].replace("]", "").strip()

            # 🔥 CLEAN LINE
            clean_line = line.split("[")[0].strip()

            clean_parts = clean_line.split()

            try:
                minute = int(clean_parts[-1])
            except:
                continue

            content = " ".join(clean_parts[:-1])

            scorer_name = None
            assist_name = None

            if "(" in content and ")" in content:
                scorer_name = content.split("(")[0].strip()
                assist_name = content.split("(")[1].replace(")", "").strip()
            else:
                scorer_name = content.strip()

            player = Player.objects.filter(
                name__icontains=scorer_name,
                club__in=[match.home_team, match.away_team],
                is_active=True
            ).first()

            assist_player = None
            if assist_name:
                assist_player = Player.objects.filter(
                    name__icontains=assist_name,
                    club__in=[match.home_team, match.away_team],
                    is_active=True
                ).first()

            if player:
                Goal.objects.create(
                    match=match,
                    player=player,
                    team=player.club,
                    minute=minute,
                    assist_player=assist_player,
                    type=goal_type  # 🔥 FIX ICI
                )

        # ---------- CARDS ----------
        for line in cards_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            try:
                minute = int(parts[-2])
            except:
                continue

            color_code = parts[-3]

            reason = "foul"
            if "[" in line and "]" in line:
                reason = line.split("[")[-1].replace("]", "").strip()

            clean_line = line.split("[")[0].strip()
            clean_parts = clean_line.split()

            player_name = " ".join(clean_parts[:-2])

            player = Player.objects.filter(
                name__icontains=player_name,
                club__in=[match.home_team, match.away_team],
                is_active=True
            ).first()

            if player:
                Card.objects.create(
                    match=match,
                    player=player,
                    team=player.club,
                    minute=minute,
                    color="red" if color_code == "R" else "yellow",
                    reason=reason
                )

        messages.success(request, "Events ajoutés.")
        return redirect(f"{request.path}?match={match.id}")

    # ======================
    # LOAD DATA
    # ======================
    goals = []
    cards = []

    if selected_match:
        goals = selected_match.goals.all().select_related("player", "team", "assist_player")
        cards = selected_match.cards.all().select_related("player", "team")

    return render(
        request,
        "admin/competitions/quick_events.html",
        {
            "competition": competition,
            "matches": matches,
            "selected_match": selected_match,
            "players": players,
            "goals": goals,
            "cards": cards,
        },
    )
@staff_member_required
def delete_goal_view(request, competition_id, goal_id):
    competition = get_object_or_404(Competition, id=competition_id)

    goal = get_object_or_404(
        Goal,
        id=goal_id,
        match__competition=competition
    )

    match_id = goal.match.id
    goal.delete()

    messages.success(request, "But supprimé.")

    return redirect(f"/admin/competitions/{competition_id}/quick-events/?match={match_id}")


@staff_member_required
def delete_card_view(request, competition_id, card_id):
    competition = get_object_or_404(Competition, id=competition_id)

    card = get_object_or_404(
        Card,
        id=card_id,
        match__competition=competition
    )

    match_id = card.match.id
    card.delete()

    messages.success(request, "Carton supprimé.")

    return redirect(f"/admin/competitions/{competition_id}/quick-events/?match={match_id}")


@staff_member_required
def update_goal_view(request, competition_id, goal_id):
    competition = get_object_or_404(Competition, id=competition_id)

    goal = get_object_or_404(
        Goal,
        id=goal_id,
        match__competition=competition
    )

    if request.method == "POST":

        minute = request.POST.get("minute")
        player_id = request.POST.get("player_id")  # 🔥 CORRECTION

        # Minute
        try:
            goal.minute = int(minute)
        except (ValueError, TypeError):
            messages.error(request, "Minute invalide.")
            return redirect(
                f"/admin/competitions/{competition_id}/quick-events/?match={goal.match.id}"
            )

        # Joueur
        if player_id:
            player = Player.objects.filter(id=player_id).first()
            if player:
                goal.player = player
                goal.team = player.club

        goal.save()
        messages.success(request, "But modifié.")

    return redirect(
        f"/admin/competitions/{competition_id}/quick-events/?match={goal.match.id}"
    )


@staff_member_required
def update_card_view(request, competition_id, card_id):
    competition = get_object_or_404(Competition, id=competition_id)

    card = get_object_or_404(
        Card,
        id=card_id,
        match__competition=competition
    )

    if request.method == "POST":

        minute = request.POST.get("minute")
        player_id = request.POST.get("player_id")  # 🔥 CORRECTION
        color = request.POST.get("color")

        # Minute
        try:
            card.minute = int(minute)
        except (ValueError, TypeError):
            messages.error(request, "Minute invalide.")
            return redirect(
                f"/admin/competitions/{competition_id}/quick-events/?match={card.match.id}"
            )

        # Joueur
        if player_id:
            player = Player.objects.filter(id=player_id).first()
            if player:
                card.player = player
                card.club = player.club

        # Couleur
        if color in ["yellow", "red"]:
            card.color = color

        card.save()
        messages.success(request, "Carton modifié.")

    return redirect(
        f"/admin/competitions/{competition_id}/quick-events/?match={card.match.id}"
    )