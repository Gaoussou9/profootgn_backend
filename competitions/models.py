from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta


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

    def __str__(self):
        return f"{self.name} – {self.competition.short_name}"


# =====================================================
# MATCH DE COMPÉTITION (AVEC CHRONO)
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

    matchday = models.PositiveIntegerField(
        default=1,
        help_text="Journée (ex: 1, 2, 3...)"
    )

    datetime = models.DateTimeField()

    home_score = models.PositiveIntegerField(default=0)
    away_score = models.PositiveIntegerField(default=0)

    # ===== CHRONO =====
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Heure réelle de démarrage du match"
    )

    elapsed_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Temps écoulé cumulé en secondes (hors pause)"
    )

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

    # =================================================
    # MÉTHODES CHRONO
    # =================================================

    def get_live_seconds(self):
        """
        Retourne le temps réel écoulé (en secondes)
        """
        if self.status == "LIVE" and self.started_at:
            delta = timezone.now() - self.started_at
            return self.elapsed_seconds + int(delta.total_seconds())
        return self.elapsed_seconds

    def get_minute_display(self):
        """
        Affichage du chrono en minutes (ex: 45', 90+2')
        """
        seconds = self.get_live_seconds()
        minutes = seconds // 60

        if minutes <= 90:
            return f"{minutes}'"
        else:
            return f"90+{minutes - 90}'"

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.competition.short_name})"


# =====================================================
# PÉNALITÉ DE POINTS (CLASSEMENT)
# =====================================================

class CompetitionPenalty(models.Model):
    """
    Permet de retirer (ou ajouter) des points à une équipe
    dans une compétition donnée
    """

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

    points = models.IntegerField(
        help_text="Nombre de points retirés (ex: -3) ou ajoutés (+1)"
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Motif de la sanction"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pénalité de points"
        verbose_name_plural = "Pénalités de points"

    def __str__(self):
        sign = "+" if self.points > 0 else ""
        return f"{self.team.name} {sign}{self.points} pts ({self.competition.short_name})"
