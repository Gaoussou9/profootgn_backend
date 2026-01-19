from competitions.models import (
    Competition,
    CompetitionMatch,
    CompetitionTeam,
)

# =====================================================
# CALCUL DU CLASSEMENT D’UNE COMPÉTITION
# =====================================================

def calculate_competition_standings(competition: Competition):
    standings = {}

    teams = CompetitionTeam.objects.filter(
        competition=competition,
        is_active=True
    )

    # =========================
    # INIT
    # =========================
    for team in teams:
        standings[team.id] = {
            "team": team,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "penalty_points": 0,
            "form": [],  # 🔥 AJOUT
        }

    # =========================
    # MATCHS PRIS EN COMPTE
    # =========================
    matches = (
        CompetitionMatch.objects
        .filter(
            competition=competition,
            status__in=["FT", "LIVE", "HT"]
        )
        .select_related("home_team", "away_team")
        .order_by("datetime")
    )

    # =========================
    # CALCUL STATS + FORME
    # =========================
    for match in matches:
        home = match.home_team
        away = match.away_team
        hs = match.home_score
        as_ = match.away_score

        # joués
        standings[home.id]["played"] += 1
        standings[away.id]["played"] += 1

        # buts
        standings[home.id]["goals_for"] += hs
        standings[home.id]["goals_against"] += as_
        standings[away.id]["goals_for"] += as_
        standings[away.id]["goals_against"] += hs

        # résultat
        if hs > as_:
            standings[home.id]["wins"] += 1
            standings[home.id]["points"] += 3
            standings[away.id]["losses"] += 1

            standings[home.id]["form"].append("V")
            standings[away.id]["form"].append("D")

        elif hs < as_:
            standings[away.id]["wins"] += 1
            standings[away.id]["points"] += 3
            standings[home.id]["losses"] += 1

            standings[away.id]["form"].append("V")
            standings[home.id]["form"].append("D")

        else:
            standings[home.id]["draws"] += 1
            standings[away.id]["draws"] += 1
            standings[home.id]["points"] += 1
            standings[away.id]["points"] += 1

            standings[home.id]["form"].append("N")
            standings[away.id]["form"].append("N")

    # =========================
    # LIMITER FORME À 5 MATCHS
    # =========================
    for team_id in standings:
        standings[team_id]["form"] = standings[team_id]["form"][-5:]

    # =========================
    # FORMAT FINAL
    # =========================
    table = []

    for data in standings.values():
        gf = data["goals_for"]
        ga = data["goals_against"]

        table.append({
            "team": data["team"],
            "played": data["played"],
            "wins": data["wins"],
            "draws": data["draws"],
            "losses": data["losses"],
            "goals_for": gf,
            "goals_against": ga,
            "goal_difference": gf - ga,
            "points": data["points"],
            "penalty_points": data["penalty_points"],
            "form": data["form"],  # 🔥 RENVOYÉ À REACT
        })

    table.sort(
        key=lambda x: (
            x["points"],
            x["goal_difference"],
            x["goals_for"],
        ),
        reverse=True
    )

    return table
