# matches/management/commands/generate_fixtures.py
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import F, Q

from datetime import date as date_cls, time as time_cls, datetime, timedelta
import re

from clubs.models import Club
from matches.models import Round, Match


def parse_iso_date(s: str) -> date_cls:
    try:
        return date_cls.fromisoformat(s)
    except Exception:
        raise CommandError("Format invalide pour --start-date. Utilise YYYY-MM-DD (ex: 2025-10-01).")


def parse_hhmm(s: str) -> time_cls:
    try:
        h, m = s.split(":")
        return time_cls(int(h), int(m))
    except Exception:
        raise CommandError("Format invalide pour --kickoff. Utilise HH:MM (ex: 16:00).")


def make_aware(dt: datetime) -> datetime:
    # Protéger contre les datetimes naïfs.
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def round_robin_pairs(teams):
    """
    Algorithme "circle method".
    Retourne une liste de journées ; chaque journée = liste de paires (home, away).
    Si nombre d'équipes impair, on ajoute un BYE (None) qui sera ignoré.
    """
    teams = list(teams)
    if len(teams) % 2 == 1:
        teams.append(None)

    n = len(teams)
    half = n // 2
    rounds = []

    cur = teams[:]  # on travaille sur une copie

    for r in range(n - 1):
        pairs = []
        for i in range(half):
            t1 = cur[i]
            t2 = cur[n - 1 - i]
            if t1 is None or t2 is None:
                # journée de repos (BYE)
                continue

            # Petite alternance home/away pour équilibrer
            if i == 0 and (r % 2 == 1):
                pairs.append((t2, t1))
            else:
                pairs.append((t1, t2))

        rounds.append(pairs)

        # rotation (en conservant le premier fixe)
        cur = [cur[0]] + [cur[-1]] + cur[1:-1]

    return rounds


def mirror_rounds(rounds):
    """Crée le retour (inversion domicile/extérieur) à partir de l'aller."""
    return [[(b, a) for (a, b) in day] for day in rounds]


def max_existing_round_number() -> int:
    """
    Détecte le plus grand numéro de journée existante de type "J<number>".
    Renvoie 0 s'il n'y en a pas.
    """
    nums = []
    for n in Round.objects.values_list("name", flat=True):
        m = re.search(r"(\d+)$", str(n))
        if m:
            try:
                nums.append(int(m.group(1)))
            except Exception:
                pass
    return max(nums) if nums else 0


class Command(BaseCommand):
    help = "Génère un calendrier (journées + matches) en round-robin pour les clubs existants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="ATTENTION : supprime toutes les journées et matchs (et donc buts/cartons liés), puis recrée.",
        )
        parser.add_argument(
            "--start-date",
            required=True,
            help="Date de départ des journées (YYYY-MM-DD), ex: 2025-10-01",
        )
        parser.add_argument(
            "--kickoff",
            default="16:00",
            help="Heure de coup d'envoi pour tous les matches (HH:MM). Défaut: 16:00",
        )
        parser.add_argument(
            "--spacing-days",
            type=int,
            default=7,
            help="Nombre de jours entre deux journées (défaut: 7).",
        )
        parser.add_argument(
            "--double",
            action="store_true",
            help="Génère aller + retour (double round-robin).",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        # Récupérer et parser les options
        start_date = parse_iso_date(opts["start_date"])
        kickoff = parse_hhmm(opts["kickoff"])
        spacing = int(opts["spacing_days"])
        make_double = bool(opts["double"])
        do_reset = bool(opts["reset"])

        # Sécurité : y a-t-il des clubs ?
        clubs = list(Club.objects.order_by("id"))
        if len(clubs) < 2:
            raise CommandError("Il faut au moins 2 clubs pour générer un calendrier.")

        # Reset si demandé
        if do_reset:
            self.stdout.write(self.style.WARNING("→ Réinitialisation demandée : suppression rounds + matches…"))
            # Matches en premier (supprime aussi Goals/Cards via CASCADE), puis Rounds
            Match.objects.all().delete()
            Round.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("✓ Base vidée (rounds & matches)."))

        # Calcule l'indice de départ des journées (si on ne reset pas, on continue)
        start_number = 1 if do_reset else (max_existing_round_number() + 1)

        # Construire l'aller
        fixtures = round_robin_pairs(clubs)
        if make_double:
            fixtures = fixtures + mirror_rounds(fixtures)

        total_days = len(fixtures)
        self.stdout.write(f"→ Génération de {total_days} journée(s)…")

        created_rounds = 0
        created_matches = 0
        skipped_matches = 0

        for day_index, pairs in enumerate(fixtures, start=0):
            round_number = start_number + day_index
            round_name = f"J{round_number}"

            # Date de la journée
            day_date = start_date + timedelta(days=spacing * day_index)
            round_obj, r_created = Round.objects.get_or_create(
                name=round_name,
                defaults={"date": day_date},
            )
            if not r_created:
                # Met à jour la date si non renseignée
                if not round_obj.date:
                    round_obj.date = day_date
                    round_obj.save(update_fields=["date"])
            created_rounds += int(r_created)

            # Datetime du coup d'envoi (même heure pour tous)
            dt = make_aware(datetime.combine(day_date, kickoff))

            for home, away in pairs:
                # Unicité garantie par ta contrainte (round, home_club, away_club)
                try:
                    match, m_created = Match.objects.get_or_create(
                        round=round_obj,
                        home_club=home,
                        away_club=away,
                        defaults={
                            "datetime": dt,
                            "home_score": 0,
                            "away_score": 0,
                            "status": "SCHEDULED",
                            "minute": 0,
                            "venue": "",
                            "buteur": "",
                        },
                    )
                except IntegrityError:
                    # Si contrainte d'unicité déclenchée : match déjà présent → on ignore
                    m_created = False
                    match = None

                if m_created:
                    created_matches += 1
                else:
                    skipped_matches += 1

        self.stdout.write(self.style.SUCCESS(
            f"✓ Terminé. Journées créées: {created_rounds} • "
            f"Matches créés: {created_matches} • Ignorés (déjà existants): {skipped_matches}"
        ))
