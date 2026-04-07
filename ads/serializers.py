from rest_framework import serializers
from .models import Ad, AdStat


class AdSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()

    class Meta:
        model = Ad
        fields = [
            "id",
            "ad_id",
            "title",
            "image",
            "video",
            "link",
            "page",
            "competition_id",
            "match_id",
            "club_id",
            "position",
            "ad_type",
            "priority",
            "active",
            "created_at",
        ]

    def get_image(self, obj):
        if obj.image:
            return obj.image.url  # ✅ simple et fonctionne toujours
        return None

    def get_video(self, obj):
        if obj.video:
            return obj.video.url
        return None


class AdStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdStat
        fields = [
            "id",
            "ad",
            "event",
            "ip",
            "user_agent",
            "created_at",
        ]
        read_only_fields = ("ip", "user_agent", "created_at")