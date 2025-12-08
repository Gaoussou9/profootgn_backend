from rest_framework import serializers
from .models import Ad, AdStat

class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = "__all__"

class AdStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdStat
        fields = "__all__"
        read_only_fields = ("ip","user_agent","created_at")
