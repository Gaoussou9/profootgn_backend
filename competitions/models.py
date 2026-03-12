from django.db import models
from django.utils.text import slugify
from django.utils import timezone


# =====================================================
# COMPÉTITION
# =====================================================

class Competition(models.Model):
    TYPE_CHOICES = (
        ("league", "Championnat"),
        ("cup", "Coupe"),
        ("supercup", "Super Coupe"),
        ("friendly", "Amical"),
    )

    CATEGORY_CHOICES = (
        ("masculin", "Masculin"),
        ("feminin", "Féminin"),
        ("informel", "Informel"),
    )

    name = models.CharField(max_length=150, unique=True)
    short_name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True, blank=True)

    logo = models.ImageField(
        upload_to="competition_logos/",
        blank=True,
        null=True,
        max_length=500
    )

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    season = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="Guinée")

    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "name"]
        indexes = [
            models.Index(fields=["category", "season"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.season}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.season})"


# =====================================================
# ÉQUIPE DANS UNE COMPÉTITION
# =====================================================

class CompetitionTeam(models.Model):
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="teams",
        db_index=True
    )

    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=50, blank=True)

    logo = models.ImageField(
        upload_to="teams/",
        blank=True,
        null=True,
        max_length=500
    )

    city = models.CharField(max_length=100, blank=True)
    coach = models.CharField(max_length=120, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("competition", "name")
        ordering = ["name"]
        verbose_name = "Équipe de compétition"
        verbose_name_plural = "Équipes de compétition"
        indexes = [
            models.Index(fields=["competition", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} – {self.competition.short_name}"


# =====================================================
# MATCH DE COMPÉTITION
# =====================================================

class CompetitionMatch(models.Model):
    STATUS_CHOICES = (
        ("SCHEDULED", "Programmé"),
        ("LIVE", "En cours"),
        ("HT", "Mi-temps"),
        ("FT", "Terminé"),
        ("POSTPONED", "Reporté"),
        ("CANCELLED", "Annulé"),
    )

    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="matches",
        db_index=True
    )

    home_team = models.ForeignKey(
        CompetitionTeam,
        on_delete=models.CASCADE,
        related_name="home_matches"
    )

    away_team = models.ForeignKey(
        CompetitionTeam,
        on_delete=models.CASCADE,
        related_name="away_matches"
    )

    matchday = models.PositiveIntegerField(default=1)
    datetime = models.DateTimeField()

    home_score = models.PositiveIntegerField(default=0)
    away_score = models.PositiveIntegerField(default=0)

    phase_start = models.DateTimeField(null=True, blank=True)
    phase_offset = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="SCHEDULED"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["matchday", "datetime"]
        verbose_name = "Match de compétition"
        verbose_name_plural = "Matchs de compétition"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(home_team=models.F("away_team")),
                name="competition_match_home_neq_away"
            )
        ]


    # =====================================================
    # CHRONO MOTEUR
    # =====================================================

    def get_live_seconds(self):
        """
        Retourne le nombre total de secondes écoulées.
        """
        seconds = self.phase_offset or 0

        if self.status == "LIVE" and self.phase_start:
            delta = timezone.now() - self.phase_start
            seconds += int(delta.total_seconds())

        return seconds

    def get_minute_display(self):
        """
        Affichage chrono football réaliste :
        0-45
        45+X
        46-90
        90+X
        """

        # Match terminé
        if self.status == "FT":
            return "Fin"

        # Mi-temps
        if self.status == "HT":
            return "Mi-temps"

        seconds = self.get_live_seconds()
        minutes = seconds // 60

        # 1ère mi-temps normale
        if minutes <= 45:
            return f"{minutes}'"

        # Temps additionnel 1ère MT
        if 45 < minutes < 60:
            return f"45+{minutes - 45}'"

        # 2e mi-temps normale
        if 60 <= minutes <= 90:
            return f"{minutes}'"

        # Temps additionnel 2e MT
        if minutes > 90:
            return f"90+{minutes - 90}'"

        return f"{minutes}'"

    def __str__(self):
        return f"{self.home_team} vs {self.away_team}"

# =====================================================
# PÉNALITÉS DE POINTS
# =====================================================

class CompetitionPenalty(models.Model):
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="penalties",
        db_index=True
    )

    team = models.ForeignKey(
        CompetitionTeam,
        on_delete=models.CASCADE,
        related_name="penalties",
        db_index=True
    )

    points = models.IntegerField()
    reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pénalité de points"
        verbose_name_plural = "Pénalités de points"

    def __str__(self):
        sign = "+" if self.points > 0 else ""
        return f"{self.team.name} {sign}{self.points} pts"
# =====================================================
# JOUEURS
# =====================================================

class Player(models.Model):
    POSITION_CHOICES = (
        ("GK", "Gardien"),
        ("DEF", "Défenseur"),
        ("MID", "Milieu"),
        ("ATT", "Attaquant"),
    )

    club = models.ForeignKey(
        CompetitionTeam,
        related_name="players",
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=100)
    number = models.PositiveIntegerField()
    position = models.CharField(max_length=10, choices=POSITION_CHOICES)

    photo = models.ImageField(
        upload_to="players/",
        blank=True,
        null=True,
        max_length=500
    )

    age = models.PositiveIntegerField(blank=True, null=True)
    nationality = models.CharField(max_length=50, blank=True)

    height = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Taille en centimètres"
    )

    previous_club_1 = models.CharField(max_length=150, blank=True)
    previous_club_2 = models.CharField(max_length=150, blank=True)
    previous_club_3 = models.CharField(max_length=150, blank=True)

    # =========================
    # STATISTIQUES
    # =========================

    matches_played = models.PositiveIntegerField(default=0)
    goals = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)
    yellow_cards = models.PositiveIntegerField(default=0)
    red_cards = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        
        indexes = [
            models.Index(fields=["club", "is_active"]),
        ]
        verbose_name = "Joueur"
        verbose_name_plural = "Joueurs"

    def __str__(self):
        return f"{self.name} #{self.number} ({self.club.name})"


# =====================================================
# BUTS
# =====================================================

class Goal(models.Model):

    match = models.ForeignKey(
        CompetitionMatch,
        related_name="goals",
        on_delete=models.CASCADE
    )

    team = models.ForeignKey(
        CompetitionTeam,
        on_delete=models.CASCADE
    )

    player = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goals_scored"
    )

    assist_player = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assists_made"
    )

    minute = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player} {self.minute}'"


# =====================================================
# CARTONS
# =====================================================

class Card(models.Model):

    COLOR_CHOICES = (
        ("yellow", "Jaune"),
        ("red", "Rouge"),
    )

    match = models.ForeignKey(
        CompetitionMatch,
        related_name="cards",
        on_delete=models.CASCADE
    )

    team = models.ForeignKey(
        CompetitionTeam,
        on_delete=models.CASCADE
    )

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="cards_received"
    )

    color = models.CharField(
        max_length=10,
        choices=COLOR_CHOICES
    )

    minute = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player} {self.color}"