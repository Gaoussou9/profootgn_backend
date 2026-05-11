from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import (
    Competition,
    CompetitionMatch,
    CompetitionTeam,
    Player,
    Goal,
    Card,
    MatchSubstitution,
)
from django.db.models import Count
from .serializers import (
    CompetitionMatchSerializer,
    CompetitionListSerializer,
)
from .services.standings import calculate_competition_standings
from .models import MatchLineup


# =====================================================
# LISTE DES COMPÉTITIONS
# =====================================================

@api_view(["GET"])
def competitions_list_api(request):
    competitions = (
        Competition.objects
        .filter(is_active=True)
        .order_by("priority", "name")
    )

    serializer = CompetitionListSerializer(
        competitions,
        many=True,
        context={"request": request}
    )

    return Response(serializer.data)


# =====================================================
# MATCHS D’UNE COMPÉTITION
# =====================================================

@api_view(["GET"])
def competition_matches_api(request, competition_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    matches = (
        CompetitionMatch.objects
        .filter(competition=competition)
        .select_related("home_team", "away_team")
        .order_by("matchday", "datetime")
    )

    serializer = CompetitionMatchSerializer(
        matches,
        many=True,
        context={"request": request}
    )

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "matches": serializer.data
    })


# =====================================================
# CLASSEMENT (AVEC FORM + PENALTY)
# =====================================================

@api_view(["GET"])
def competition_standings_api(request, competition_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    table = calculate_competition_standings(competition)

    standings = []
    position = 1

    for row in table:
        team = row["team"]

        standings.append({
            "position": position,
            "team": {
                "id": team.id,
                "name": team.name,
                "logo": (
                    request.build_absolute_uri(team.logo.url)
                    if getattr(team, "logo", None)
                    else None
                ),
            },
            "played": row["played"],
            "wins": row["wins"],
            "draws": row["draws"],
            "losses": row["losses"],
            "goals_for": row["goals_for"],
            "goals_against": row["goals_against"],
            "goal_difference": row["goal_difference"],
            "points": row["points"],
            "penalty_points": row.get("penalty_points", 0),
            "form": row.get("form", []),
        })

        position += 1

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "standings": standings
    })


# =====================================================
# CLUBS
# =====================================================

@api_view(["GET"])
def competition_clubs_api(request, competition_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    teams = CompetitionTeam.objects.filter(
        competition=competition,
        is_active=True
    )

    clubs = []

    for club in teams:
        clubs.append({
            "id": club.id,
            "name": club.name,
            "logo": (
                request.build_absolute_uri(club.logo.url)
                if getattr(club, "logo", None)
                else None
            ),
        })

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "clubs": clubs
    })


# =====================================================
# DETAIL CLUB (AVEC STATS AJOUTÉES)
# =====================================================

@api_view(["GET"])
def competition_club_detail_api(request, competition_id, club_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    club = get_object_or_404(
        CompetitionTeam,
        id=club_id,
        competition=competition,
        is_active=True
    )

    # 🔥 On récupère le classement pour trouver les stats du club
    table = calculate_competition_standings(competition)

    stats_data = None
    position = 1

    for row in table:
        if row["team"].id == club.id:
            stats_data = {
                "position": position,
                "played": row["played"],
                "wins": row["wins"],
                "draws": row["draws"],
                "losses": row["losses"],
                "goal_difference": row["goal_difference"],
                "points": row["points"],
            }
            break
        position += 1

    return Response({
        "club": {
            "id": club.id,
            "name": club.name,
            "short_name": club.short_name,
            "logo": (
                request.build_absolute_uri(club.logo.url)
                if getattr(club, "logo", None)
                else None
            ),
            "city": club.city,
        },
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },
        "stats": stats_data
    })


# =====================================================
# MATCHS D’UN CLUB
# =====================================================

@api_view(["GET"])
def competition_club_matches_api(request, competition_id, club_id):
    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    club = get_object_or_404(
        CompetitionTeam,
        id=club_id,
        competition=competition,
        is_active=True
    )

    matches = (
        CompetitionMatch.objects
        .filter(competition=competition)
        .filter(Q(home_team=club) | Q(away_team=club))
        .select_related("home_team", "away_team")
        .order_by("-datetime")
    )

    serializer = CompetitionMatchSerializer(
        matches,
        many=True,
        context={"request": request}
    )

    return Response(serializer.data)


@api_view(["GET"])
def competition_match_detail(
    request,
    competition_id,
    match_id
):

    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    match = get_object_or_404(
        CompetitionMatch.objects.prefetch_related(
            "goals__player",
            "goals__assist_player",
            "cards__player",
            "substitutions__player_out",
            "substitutions__player_in",
        ),
        id=match_id,
        competition=competition
    )

    serializer = CompetitionMatchSerializer(
        match,
        context={"request": request}
    )

    data = serializer.data

    # =========================
    # SUBSTITUTIONS
    # =========================

    data["substitutions"] = [

        {

            "id": sub.id,

            "minute": sub.minute,

            "team": sub.team.id,

            "player_out": {

                "id": sub.player_out.id,

                "club_id": sub.player_out.club.id,

                "name": sub.player_out.name,

                "photo": (
                    request.build_absolute_uri(
                        sub.player_out.photo.url
                    )
                    if getattr(
                        sub.player_out,
                        "photo",
                        None
                    )
                    else None
                )
            },

            "player_in": {

                "id": sub.player_in.id,

                "club_id": sub.player_in.club.id,

                "name": sub.player_in.name,

                "photo": (
                    request.build_absolute_uri(
                        sub.player_in.photo.url
                    )
                    if getattr(
                        sub.player_in,
                        "photo",
                        None
                    )
                    else None
                )
            }

        }

        for sub in MatchSubstitution.objects.filter(
            match=match
        ).select_related(
            "player_out",
            "player_in",
            "team"
        )

    ]

    return Response(data)

# =====================================================
# JOUEURS D’UN CLUB
# =====================================================
@api_view(["GET"])
def competition_club_players_api(request, competition_id, club_id):

    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    club = get_object_or_404(
        CompetitionTeam,
        id=club_id,
        competition=competition,
        is_active=True
    )

    players = (
        club.players
        .filter(is_active=True)
        .order_by("number")
    )

    data = []

    for player in players:

        # =========================
        # STATS EVENTS
        # =========================

        event_goals = Goal.objects.filter(
            player=player,
            match__competition=competition
        ).count()

        event_assists = Goal.objects.filter(
            assist_player=player,
            match__competition=competition
        ).count()

        yellow_cards = Card.objects.filter(
            player=player,
            match__competition=competition,
            color="yellow"
        ).count()

        red_cards = Card.objects.filter(
            player=player,
            match__competition=competition,
            color="red"
        ).count()

        # =========================
        # PHOTO
        # =========================

        photo = None

        if getattr(player, "photo", None):
            try:
                photo = request.build_absolute_uri(
                    player.photo.url
                )
            except:
                photo = None

        # =========================
        # DATA
        # =========================

        data.append({

            "id": player.id,

            "name": player.name,

            "number": player.number,

            "position": player.position,

            "photo": photo,

            # 🔥 STATS HYBRIDES
            "matches_played": getattr(
                player,
                "matches_played",
                0
            ),

            "goals": (
                getattr(player, "goals", 0)
                + event_goals
            ),

            "assists": (
                getattr(player, "assists", 0)
                + event_assists
            ),

            "yellow_cards": (
                getattr(player, "yellow_cards", 0)
                + yellow_cards
            ),

            "red_cards": (
                getattr(player, "red_cards", 0)
                + red_cards
            ),
        })

    return Response({
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "season": competition.season,
        },

        "club": {
            "id": club.id,
            "name": club.name,
        },

        "players": data
    })


# =====================================================
# DETAILS PLAYER
# =====================================================

@api_view(["GET"])
def competition_player_detail_api(
    request,
    competition_id,
    club_id,
    player_id
):

    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    club = get_object_or_404(
        CompetitionTeam,
        id=club_id,
        competition=competition,
        is_active=True
    )

    player = get_object_or_404(
        Player,
        id=player_id,
        club=club,
        is_active=True
    )

    # =========================
    # STATS EVENTS
    # =========================

    event_goals = Goal.objects.filter(
        player=player,
        match__competition=competition
    ).count()

    event_assists = Goal.objects.filter(
        assist_player=player,
        match__competition=competition
    ).count()

    yellow_cards = Card.objects.filter(
        player=player,
        match__competition=competition,
        color="yellow"
    ).count()

    red_cards = Card.objects.filter(
        player=player,
        match__competition=competition,
        color="red"
    ).count()

    # =========================
    # PHOTO
    # =========================

    photo = None

    if getattr(player, "photo", None):

        try:

            photo = request.build_absolute_uri(
                player.photo.url
            )

        except:

            photo = None

    # =========================
    # CLUB LOGO
    # =========================

    club_logo = None

    if getattr(club, "logo", None):

        try:

            club_logo = request.build_absolute_uri(
                club.logo.url
            )

        except:

            club_logo = None

    return Response({

        "id": player.id,

        "name": player.name,

        "number": player.number,

        "position": player.position,

        "photo": photo,

        "age": player.age,

        "nationality": player.nationality,

        "height": player.height,

        "previous_club_1": player.previous_club_1,

        "previous_club_2": player.previous_club_2,

        "previous_club_3": player.previous_club_3,

        # =========================
        # STATS
        # =========================

        "matches_played": getattr(
            player,
            "matches_played",
            0
        ),

        "goals": (
            getattr(player, "goals", 0)
            + event_goals
        ),

        "assists": (
            getattr(player, "assists", 0)
            + event_assists
        ),

        "yellow_cards": (
            getattr(player, "yellow_cards", 0)
            + yellow_cards
        ),

        "red_cards": (
            getattr(player, "red_cards", 0)
            + red_cards
        ),

        "club": {

            "id": club.id,

            "name": club.name,

            "logo": club_logo,
        }
    })


# =====================================================
# CLASSEMENT DES BUTEURS
# =====================================================

@api_view(["GET"])
def competition_top_scorers_api(
    request,
    competition_id
):

    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    players = (
        Player.objects
        .filter(
            club__competition_id=competition.id,
            is_active=True
        )
        .select_related("club")
    )

    data = []

    for player in players:

        # =========================
        # BUTS
        # =========================

        manual_goals = getattr(
            player,
            "goals",
            0
        ) or 0

        event_goals = Goal.objects.filter(
            player=player,
            match__competition=competition
        ).count()

        total_goals = (
            manual_goals
            + event_goals
        )

        # ignorer joueurs sans but
        if total_goals <= 0:
            continue

        # =========================
        # ASSISTS
        # =========================

        manual_assists = getattr(
            player,
            "assists",
            0
        ) or 0

        event_assists = Goal.objects.filter(
            assist_player=player,
            match__competition=competition
        ).count()

        total_assists = (
            manual_assists
            + event_assists
        )

        # =========================
        # MATCHS JOUÉS
        # =========================

        matches_played = getattr(
            player,
            "matches_played",
            0
        ) or 0

        # =========================
        # RATIO
        # =========================

        ratio = round(
            total_goals / matches_played,
            2
        ) if matches_played > 0 else 0

        # =========================
        # PHOTO JOUEUR
        # =========================

        photo = None

        if getattr(player, "photo", None):

            try:

                photo = request.build_absolute_uri(
                    player.photo.url
                )

            except:

                photo = None

        # =========================
        # LOGO CLUB
        # =========================

        logo = None

        if getattr(player.club, "logo", None):

            try:

                logo = request.build_absolute_uri(
                    player.club.logo.url
                )

            except:

                logo = None

        # =========================
        # DATA
        # =========================

        data.append({

            "id": player.id,

            "name": player.name,

            "goals": total_goals,

            "matches_played": matches_played,

            "ratio": ratio,

            "assists": total_assists,

            "photo": photo,

            "club": {

                "id": player.club.id,

                "name": player.club.name,

                "logo": logo,
            }
        })

    # =========================
    # TRI
    # =========================

    data = sorted(
        data,
        key=lambda x: (
            -x["goals"],
            x["name"]
        )
    )

    # =========================
    # RANKING
    # =========================

    for i, row in enumerate(
        data,
        start=1
    ):

        row["rank"] = i

    return Response({

        "competition": {

            "id": competition.id,

            "name": competition.name,

            "season": competition.season,
        },

        "scorers": data
    })    
# =====================================================
# JOUEURS D’UN MATCH (🔥 IMPORTANT)
# =====================================================

@api_view(["GET"])
def match_players_api(request, match_id):
    match = get_object_or_404(CompetitionMatch, id=match_id)

    players = Player.objects.filter(
        club__in=[match.home_team, match.away_team],
        is_active=True
    ).select_related("club")

    data = [
        {
            "id": p.id,
            "name": p.name,
            "club_id": p.club.id,
            "club_name": p.club.name,
        }
        for p in players
    ]

    return Response(data)

@api_view(["GET"])
def competition_match_lineups_api(
    request,
    competition_id,
    match_id
):

    competition = get_object_or_404(
        Competition,
        id=competition_id,
        is_active=True
    )

    match = get_object_or_404(
        CompetitionMatch,
        id=match_id,
        competition=competition
    )

    lineups = MatchLineup.objects.filter(
        match=match
    ).select_related(
        "player",
        "team"
    )

    home_starters = []
    away_starters = []

    home_subs = []
    away_subs = []

    for lineup in lineups:

        player = lineup.player

        photo = None

        if getattr(player, "photo", None):

            try:

                photo = request.build_absolute_uri(
                    player.photo.url
                )

            except:

                photo = None

        player_data = {

            "id": player.id,

            "club_id": player.club.id,

            "name": player.name,

            "number": player.number,

            "photo": photo,

            "position": lineup.position,

            "is_captain": lineup.is_captain,

            "is_goalkeeper": lineup.is_goalkeeper,

            "rating": lineup.rating,

            "is_player_of_match": lineup.man_of_match,
    

            # =========================
            # COORDONNÉES TERRAIN
            # =========================

            "x": lineup.x,

            "y": lineup.y,
        }

        # =========================
        # DOMICILE
        # =========================

        if lineup.team.id == match.home_team.id:

            if lineup.is_starter:

                home_starters.append(
                    player_data
                )

            else:

                home_subs.append(
                    player_data
                )

        # =========================
        # EXTÉRIEUR
        # =========================

        else:

            if lineup.is_starter:

                away_starters.append(
                    player_data
                )

            else:

                away_subs.append(
                    player_data
                )

    return Response({

        # =========================
        # ÉQUIPES
        # =========================

        "home_team": {

            "id": match.home_team.id,

            "name": match.home_team.name,
        },

        "away_team": {

            "id": match.away_team.id,

            "name": match.away_team.name,
        },

        # =========================
        # FORMATIONS
        # =========================

        "home_formation":
            match.home_formation,

        "away_formation":
            match.away_formation,

        # =========================
        # TITULAIRES
        # =========================

        "home_starters":
            home_starters,

        "away_starters":
            away_starters,

        # =========================
        # REMPLAÇANTS
        # =========================

        "home_substitutes":
            home_subs,

        "away_substitutes":
            away_subs,
    })