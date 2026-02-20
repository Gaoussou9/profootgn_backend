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

    started_at = models.DateTimeField(null=True, blank=True)
    elapsed_seconds = models.PositiveIntegerField(default=0)

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

    def get_live_seconds(self):
        if self.status == "LIVE" and self.started_at:
            delta = timezone.now() - self.started_at
            return self.elapsed_seconds + int(delta.total_seconds())
        return self.elapsed_seconds

    def get_minute_display(self):
        seconds = self.get_live_seconds()
        minutes = seconds // 60
        return f"{minutes}'" if minutes <= 90 else f"90+{minutes - 90}'"

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

    # 🔥 NOUVEAUX CHAMPS
    height = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Taille en centimètres"
    )

    previous_club_1 = models.CharField(max_length=150, blank=True)
    previous_club_2 = models.CharField(max_length=150, blank=True)
    previous_club_3 = models.CharField(max_length=150, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        unique_together = ("club", "number")
        indexes = [
            models.Index(fields=["club", "is_active"]),
        ]
        verbose_name = "Joueur"
        verbose_name_plural = "Joueurs"

    def __str__(self):
        return f"{self.name} #{self.number} ({self.club.name})"