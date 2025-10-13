# clubs/models.py
from django.db import models


class Club(models.Model):
    name = models.CharField(max_length=120, unique=True)
    short_name = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    founded = models.DateField(null=True, blank=True)
    stadium = models.CharField(max_length=120, blank=True)
    # ⬇️ augmenter max_length (Cloudinary peut dépasser 100)
    logo = models.ImageField(upload_to="logos/", blank=True, null=True, max_length=500)
    president = models.CharField(max_length=120, blank=True)
    coach = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StaffMember(models.Model):
    ROLES = [
        ("PRESIDENT", "Président"),
        ("COACH", "Entraîneur principal"),
        ("ASSIST_COACH", "Adjoint"),
        ("DIRECTOR", "Directeur sportif"),
        ("TEAM_MANAGER", "Team manager"),
        ("PHYSIO", "Kinésithérapeute"),
        ("GK_COACH", "Coach gardiens"),
        ("ANALYST", "Analyste vidéo"),
        ("KIT_MANAGER", "Intendant"),
    ]
    club      = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="staff")
    full_name = models.CharField(max_length=120)
    role      = models.CharField(max_length=20, choices=ROLES)
    phone     = models.CharField(max_length=40, blank=True)
    email     = models.EmailField(blank=True)
    # ⬇️ idem : augmenter max_length
    photo     = models.ImageField(upload_to="staff/", null=True, blank=True, max_length=500)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["club", "role", "full_name"])]

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
