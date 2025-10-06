from django import forms
from .models import Match, Club

class MatchQuickForm(forms.Form):
    home_club = forms.ModelChoiceField(
        queryset=Club.objects.all(),
        label="Équipe 1",
        widget=forms.Select(attrs={"placeholder": "Équipe 1"})
    )
    away_club = forms.ModelChoiceField(
        queryset=Club.objects.all(),
        label="Équipe 2",
        widget=forms.Select(attrs={"placeholder": "Équipe 2"})
    )
    home_score = forms.IntegerField(label="Score équipe 1", min_value=0, initial=0)
    away_score = forms.IntegerField(label="Score équipe 2", min_value=0, initial=0)
    minute = forms.IntegerField(label="Minute (ex: 78')", required=False, min_value=0)
    scorers = forms.CharField(
        label="Buteurs",
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 2,
            "placeholder": "Format libre. Ex: 12' Diallo (Milo); 54' Camara (WAC)"
        })
    )
    STATUS_CHOICES = [
        ("SCHEDULED", "Programmé"),
        ("LIVE", "En direct"),
        ("FINISHED", "Terminé"),
    ]
    status = forms.ChoiceField(choices=STATUS_CHOICES, label="Statut", initial="SCHEDULED")

    # Optionnel: date/lieu si tu veux les saisir ici
    # datetime = forms.DateTimeField(required=False, label="Date/Heure")
    # venue = forms.CharField(required=False, label="Stade")
