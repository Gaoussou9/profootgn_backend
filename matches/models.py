from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

from clubs.models import Club
from players.models import Player

# -----------------------------------
# Statuts (cohérents admin/front)
# -----------------------------------
MATCH_STATUS = [
    ("SCHEDULED", "Scheduled"),
    ("LIVE", "Live"),
    ("HT", "Half-time"),
    ("PAUSED", "Paused"),
    ("FT", "Full-time"),
    ("FINISHED", "Finished"),
    ("SUSPENDED", "Suspended"),
    ("POSTPONED", "Postponed"),
    ("CANCELED", "Canceled"),
]


# -----------------------------------
# Round (journée)
# -----------------------------------
class Round(models.Model):
    name = models.CharField(max_length=50)  # ex. "Journée 1" ou "J1"
    date = models.DateField(null=True, blank=True)
    number = models.PositiveIntegerField(
        null=True, blank=True, unique=True
    )  # ex. 1..26

    class Meta:
        ordering = ["number", "id"]

    @property
    def display_name(self):
        if self.number:
            return f"J{self.number}"
        return self.name or f"J?{self.pk}"

    def __str__(self):
        return self.display_name


# -----------------------------------
# Match
# -----------------------------------
class Match(models.Model):
    round = models.ForeignKey(
        Round, on_delete=models.SET_NULL, null=True, related_name="matches"
    )
    datetime = models.DateTimeField()

    home_club = models.ForeignKey(
        Club, on_delete=models.CASCADE, related_name="home_matches"
    )
    away_club = models.ForeignKey(
        Club, on_delete=models.CASCADE, related_name="away_matches"
    )

    home_score = models.PositiveIntegerField(default=0)
    away_score = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=12, choices=MATCH_STATUS, default="SCHEDULED")

    # minute "manuelle" historique (garde-le pour compat si tu remplis ça aujourd'hui)
    minute = models.PositiveIntegerField(default=0)

    venue = models.CharField(max_length=120, blank=True)

    # Champ libre admin (optionnel)
    buteur = models.CharField(
        max_length=120, blank=True, default="", help_text="Nom du buteur principal"
    )

    # ⬇⬇ NOUVEAU : horodatages réels des coups d'envoi, utilisés pour calculer la minute côté serveur
    kickoff_1 = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Heure réelle du début de la 1ère mi-temps (UTC).",
    )
    kickoff_2 = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Heure réelle du début de la 2ème mi-temps (UTC).",
    )

    class Meta:
        ordering = ["datetime"]
        constraints = [
            # Interdit home == away
            models.CheckConstraint(
                check=~models.Q(home_club=models.F("away_club")),
                name="match_home_neq_away",
            ),
            # Doublon exact (même sens) interdit dans une journée
            models.UniqueConstraint(
                fields=["round", "home_club", "away_club"],
                name="uniq_round_home_away_in_round",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.home_club_id
            and self.away_club_id
            and self.home_club_id == self.away_club_id
        ):
            raise ValidationError(
                "Le club à domicile ne peut pas être identique au club à l'extérieur."
            )

        # Empêche aussi l'affiche inversée dans la même journée (A-B et B-A)
        if self.round_id and self.home_club_id and self.away_club_id:
            qs = Match.objects.filter(round_id=self.round_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            exists_same = qs.filter(
                home_club_id=self.home_club_id, away_club_id=self.away_club_id
            ).exists()
            exists_reverse = qs.filter(
                home_club_id=self.away_club_id, away_club_id=self.home_club_id
            ).exists()
            if exists_same or exists_reverse:
                raise ValidationError(
                    "Une affiche entre ces deux clubs existe déjà pour cette journée (même sens ou inversée)."
                )

    def __str__(self):
        return f"{self.home_club} vs {self.away_club}"


# -----------------------------------
# Buts & Cartons
# -----------------------------------
class Goal(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="goals")
    player = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True
    )
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    minute = models.PositiveIntegerField()

    # Assist : soit joueur, soit nom libre
    assist_player = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name="assists"
    )
    assist_name = models.CharField(max_length=120, blank=True, default="")

    # Champs facultatifs pour tags (penalty/CSC) si tes serializers les utilisent
    type = models.CharField(max_length=12, blank=True, default="")  # "PEN", "OG", etc.

    def __str__(self):
        who = self.player or self.assist_name or f"#{self.pk}"
        return f"{who} {self.minute}'"


CARD_TYPES = [("Y", "Yellow"), ("R", "Red")]


class Card(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="cards")
    player = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True
    )
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    minute = models.PositiveIntegerField()
    # L'admin/serializer peuvent mapper "color"/"card_type" -> type
    type = models.CharField(max_length=1, choices=CARD_TYPES)

    def __str__(self):
        return f"{self.player} {self.get_type_display()} {self.minute}'"


# -----------------------------------
# Infos d'équipe par match (formation / coach)
# -----------------------------------
class TeamInfoPerMatch(models.Model):
    """
    Une ligne par (match, club). Sert à afficher formation & coach côté front.
    """
    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="team_infos"
    )
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    formation = models.CharField(max_length=20, blank=True, default="")  # "4-3-3"
    coach_name = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        unique_together = ("match", "club")
        verbose_name = "Team info per match"
        verbose_name_plural = "Team info per matches"

    def __str__(self):
        return f"{self.match} • {self.club} • {self.formation or '—'}"


# -----------------------------------
# Lineup (compositions)
# -----------------------------------
class Lineup(models.Model):
    """
    Une ligne = un joueur (ou un nom libre) pour ce match/club.
    Champs pensés pour correspondre au front + serializers.
    """
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="lineups")
    club = models.ForeignKey(Club, on_delete=models.CASCADE)

    # Lien optionnel vers Player + nom libre (si pas de Player attaché)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)
    player_name = models.CharField(max_length=120, blank=True, default="")

    # Détails d’affichage
    number = models.IntegerField(null=True, blank=True)      # maillot
    position = models.CharField(max_length=8, blank=True, default="")  # GK/CB/DM/AM/RW/LW/ST...
    is_starting = models.BooleanField(default=True)          # titulaire ?
    is_captain = models.BooleanField(default=False)

    # Champ conservé mais non bloquant (ignoré par les validations)
    minutes_played = models.PositiveIntegerField(
        default=0, help_text="Minutes jouées (optionnel, ignoré pour la note)"
    )

    # ✅ Note/Rating: 1.0–10.0 ; NULL si pas de note
    # IMPORTANT: max_digits=4 (ex: 10.0)
    rating = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(10.0)],
        help_text="Note de match (1.0 à 10.0). Laisser vide s'il n'y a pas de note."
    )

    # Photo côté lineup : une URL (si fournie). Sinon, le serializer peut retomber sur Player.photo
    photo = models.URLField(max_length=300, blank=True, default="")

    class Meta:
        # Tri stable attendu par le front : club -> titulaires -> numéro -> id
        ordering = ["club_id", "-is_starting", "number", "id"]
        indexes = [
            models.Index(fields=["match", "club"]),
            models.Index(fields=["match", "club", "is_starting"]),
        ]

    def clean(self):
        super().clean()
        # ✅ On autorise un rating même si minutes_played == 0
        # On garde uniquement le bornage de la note
        if self.rating is not None:
            r = float(self.rating)
            if not (1.0 <= r <= 10.0):
                raise ValidationError("Le rating doit être entre 1.0 et 10.0.")

    def __str__(self):
        name = (
            self.player_name
            or getattr(self.player, "name", "")
            or f"#{self.number or '?'}"
        )
        tag = "XI" if self.is_starting else "SUB"
        return f"{self.match_id}:{self.club_id} {tag} {name}"
