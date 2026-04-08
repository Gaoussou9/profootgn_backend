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

    # 🔥 méthode réutilisable (clean code)
    def build_media_url(self, file_field):
        if not file_field:
            return None

        try:
            request = self.context.get("request")
            url = file_field.url

            # ✅ prod (URL absolue)
            if request:
                return request.build_absolute_uri(url)

            # ✅ fallback local
            return url

        except Exception:
            return None

    def get_image(self, obj):
        return self.build_media_url(obj.image)

    def get_video(self, obj):
        return self.build_media_url(obj.video)


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