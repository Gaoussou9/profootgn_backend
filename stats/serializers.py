
from rest_framework import serializers

class StandingRowSerializer(serializers.Serializer):
    club_id = serializers.IntegerField()
    club_name = serializers.CharField()
    played = serializers.IntegerField()
    wins = serializers.IntegerField()
    draws = serializers.IntegerField()
    losses = serializers.IntegerField()
    goals_for = serializers.IntegerField()
    goals_against = serializers.IntegerField()
    goal_diff = serializers.IntegerField()
    points = serializers.IntegerField()

class TopScorerSerializer(serializers.Serializer):
    player_id = serializers.IntegerField()
    player_name = serializers.CharField()
    club_name = serializers.CharField()
    goals = serializers.IntegerField()
