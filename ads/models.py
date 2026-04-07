from django.db import models


class Ad(models.Model):
    POSITION_CHOICES = [
        ("top", "Haut"),
        ("middle", "Milieu"),
        ("bottom", "Bas"),
    ]

    TYPE_CHOICES = [
        ("image", "Image"),
        ("video", "Vidéo"),
    ]

    ad_id = models.CharField(max_length=120, unique=True)
    title = models.CharField(max_length=255, blank=True, null=True)

    image = models.ImageField(upload_to="ads/images/", blank=True, null=True)
    video = models.FileField(upload_to="ads/videos/", blank=True, null=True)
    link = models.URLField(blank=True, null=True)

    # 🎯 CIBLAGE
    page = models.CharField(max_length=100, blank=True, null=True)
    competition_id = models.IntegerField(blank=True, null=True)
    match_id = models.IntegerField(blank=True, null=True)
    club_id = models.IntegerField(blank=True, null=True)

    # 📍 POSITION
    position = models.CharField(max_length=50, choices=POSITION_CHOICES, default="top")

    # 🎬 TYPE
    ad_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="image")

    # ⭐ PRIORITÉ (BUSINESS 💰)
    priority = models.IntegerField(default=1)

    # ✅ STATUT
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["page", "position", "active"]),
            models.Index(fields=["competition_id"]),
            models.Index(fields=["match_id"]),
            models.Index(fields=["club_id"]),
        ]

    def __str__(self):
        return f"{self.ad_id} - {self.page or 'global'}"


# 📊 STATISTIQUES (TRÈS IMPORTANT POUR BUSINESS)
class AdStat(models.Model):
    EVENT_CHOICES = (
        ("impression", "impression"),
        ("click", "click"),
    )

    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name="stats")
    event = models.CharField(max_length=20, choices=EVENT_CHOICES)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["ad", "event", "created_at"]),
        ]

    def __str__(self):
        return f"{self.ad.ad_id} - {self.event}"