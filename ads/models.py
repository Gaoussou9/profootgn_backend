from django.db import models

class Ad(models.Model):
    ad_id = models.CharField(max_length=120, unique=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    image = models.URLField(blank=True, null=True)
    video = models.URLField(blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ad_id

class AdStat(models.Model):
    EVENT_CHOICES = (("impression","impression"), ("click","click"))
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name="stats")
    event = models.CharField(max_length=20, choices=EVENT_CHOICES)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["ad","event","created_at"]),
        ]

    def __str__(self):
        return f"{self.ad.ad_id} - {self.event} @ {self.created_at}"
