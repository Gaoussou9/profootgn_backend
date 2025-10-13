# players/models.py
from django.db import models
from clubs.models import Club

POSITIONS = [
    ("GK", "Goalkeeper"),
    ("DF", "Defender"),
    ("MF", "Midfielder"),
    ("FW", "Forward"),
]

class Player(models.Model):
    first_name  = models.CharField(max_length=80)
    last_name   = models.CharField(max_length=80, blank=True)  # certains joueurs n'ont pas toujours de nom saisi
    club        = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        related_name="players",
        db_index=True,
    )
    number      = models.PositiveIntegerField(default=0)
    # Si tu veux autoriser texte libre: laisse sans choices
    # Si tu préfères limiter aux 4 rôles ci-dessus, ajoute choices=POSITIONS
    position    = models.CharField(max_length=64, blank=True, null=True)  # choices=POSITIONS,
    nationality = models.CharField(max_length=60, blank=True)
    birthdate   = models.DateField(null=True, blank=True)

    # ✅ Cloudinary: URL longue possible
    photo       = models.ImageField(
        upload_to="players/",
        blank=True,
        null=True,
        max_length=500,
    )

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["club", "last_name", "first_name"]),
            models.Index(fields=["position"]),
        ]
        # Si tu veux interdire deux joueurs avec le même numéro dans le même club, décommente:
        # constraints = [
        #     models.UniqueConstraint(fields=["club", "number"], name="uniq_jersey_per_club"),
        # ]

    def __str__(self):
        # gère le cas où last_name est vide
        full = f"{self.first_name} {self.last_name or ''}".strip()
        return full
