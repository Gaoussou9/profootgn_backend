
from django.db import models
from clubs.models import Club
from players.models import Player

class Recruiter(models.Model):
    name = models.CharField(max_length=120)
    organization = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.name

class TrialRequest(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='trial_requests')
    recruiter = models.ForeignKey(Recruiter, on_delete=models.CASCADE, related_name='trial_requests')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending')  # pending/accepted/rejected

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.player} - {self.recruiter}"
