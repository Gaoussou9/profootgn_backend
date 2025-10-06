# clubs/serializers.py
from rest_framework import serializers
from .models import Club, StaffMember

class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = [
            "id", "name", "short_name", "city", "founded",
            "stadium", "logo", "president", "coach"
        ]


class ClubMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ["id", "name", "logo"]


class StaffSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    full_name = serializers.SerializerMethodField()   # ✅ calculé si pas présent en DB
    # (optionnel) URL absolue de la photo :
    # photo_url = serializers.SerializerMethodField()

    class Meta:
        model = StaffMember
        fields = [
            "id", "club", "club_name", "full_name", "role",
            "role_display", "phone", "email", "photo", "is_active",
            # "photo_url",
        ]

    def get_full_name(self, obj):
        # 1) s'il existe un attr/prop 'full_name' non vide, on l'utilise
        fn = getattr(obj, "full_name", None)
        if isinstance(fn, str) and fn.strip():
            return fn.strip()
        # 2) sinon 'name' si présent
        name = (getattr(obj, "name", "") or "").strip()
        if name:
            return name
        # 3) sinon concat first/last
        first = (getattr(obj, "first_name", "") or "").strip()
        last  = (getattr(obj, "last_name", "") or "").strip()
        value = (first + " " + last).strip()
        return value or None

    # def get_photo_url(self, obj):
    #     request = self.context.get("request")
    #     try:
    #         return request.build_absolute_uri(obj.photo.url) if (request and obj.photo) else None
    #     except Exception:
    #         return None
