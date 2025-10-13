
from django.db import models
from clubs.models import Club

POSITIONS = [
    ('GK','Goalkeeper'),
    ('DF','Defender'),
    ('MF','Midfielder'),
    ('FW','Forward'),
]

class Player(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, related_name='players')
    number = models.PositiveIntegerField(default=0)
    position = models.CharField(max_length=64, blank=True, null=True) 
    nationality = models.CharField(max_length=60, blank=True)
    birthdate = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='players/', blank=True, null=True, max_length=500,)

    class Meta:
        ordering = ['last_name','first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
