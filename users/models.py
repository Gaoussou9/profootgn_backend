
from django.db import models
from django.contrib.auth.models import User
from clubs.models import Club

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    favorite_club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True)
    bio = models.CharField(max_length=240, blank=True)

    def __str__(self):
        return self.user.username
