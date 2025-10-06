
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command

class Command(BaseCommand):
    help = "Charge les données de démonstration (fixtures)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Chargement des fixtures..."))
        try:
            call_command('loaddata', 'clubs/fixtures/clubs.json')
            call_command('loaddata', 'players/fixtures/players.json')
            call_command('loaddata', 'matches/fixtures/rounds.json')
            call_command('loaddata', 'matches/fixtures/matches.json')
            call_command('loaddata', 'matches/fixtures/goals.json')
        except Exception as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS("Données de démo chargées."))
