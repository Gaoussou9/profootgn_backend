import random
from ..models import CompetitionMatch

ROUND_NAMES = {
    32: "16e",
    16: "Huitièmes",
    8: "Quarts",
    4: "Demis",
    2: "Finale",
}

def generate_cup_bracket(competition):

    teams = list(competition.teams.all())

    random.shuffle(teams)

    total = len(teams)

    if total not in ROUND_NAMES:
        raise ValueError("Nombre d'équipes invalide pour une coupe")

    round_name = ROUND_NAMES[total]

    matches = []

    for i in range(0, total, 2):

        home = teams[i]
        away = teams[i + 1]

        match = CompetitionMatch.objects.create(
            competition=competition,
            home_team=home,
            away_team=away,
            round=round_name,
        )

        matches.append(match)

    return matches