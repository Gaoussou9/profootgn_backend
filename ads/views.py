from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.db.models.functions import TruncDate

from .models import Ad, AdStat
from .serializers import AdSerializer


# 🔥 LIST ADS (INTELLIGENT + SAFE PROD)
@api_view(["GET"])
def list_ads(request):
    page = request.query_params.get("page")
    position = request.query_params.get("position")

    # 🔐 sécurisation des IDs (évite "undefined")
    def safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    competition_id = safe_int(request.query_params.get("competition_id"))
    match_id = safe_int(request.query_params.get("match_id"))
    club_id = safe_int(request.query_params.get("club_id"))

    ads = Ad.objects.filter(active=True)

    # 🎯 filtres principaux
    if page:
        ads = ads.filter(page=page)

    if position:
        ads = ads.filter(position=position)

    # 🎯 ciblage avancé
    targeting_filter = Q()

    if competition_id:
        targeting_filter |= Q(competition_id=competition_id)

    if match_id:
        targeting_filter |= Q(match_id=match_id)

    if club_id:
        targeting_filter |= Q(club_id=club_id)

    # 🌍 fallback global
    targeting_filter |= Q(
        competition_id__isnull=True,
        match_id__isnull=True,
        club_id__isnull=True
    )

    ads = (
        ads
        .filter(targeting_filter)
        .order_by("-priority")  # 💰 sponsor en premier
        .distinct()
    )

    # ✅ CRITIQUE POUR PROD (images/vidéos)
    serializer = AdSerializer(ads, many=True, context={"request": request})

    return Response(serializer.data)


# 📊 LOG IMPRESSION
@api_view(["POST"])
@permission_classes([AllowAny])
def log_impression(request):
    ad_id = request.data.get("ad_id")

    if not ad_id:
        return Response({"detail": "ad_id required"}, status=status.HTTP_400_BAD_REQUEST)

    ad = get_object_or_404(Ad, ad_id=ad_id, active=True)

    AdStat.objects.create(
        ad=ad,
        event="impression",
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")
    )

    return Response({"ok": True})


# 📊 LOG CLICK
@api_view(["POST"])
@permission_classes([AllowAny])
def log_click(request):
    ad_id = request.data.get("ad_id")

    if not ad_id:
        return Response({"detail": "ad_id required"}, status=status.HTTP_400_BAD_REQUEST)

    ad = get_object_or_404(Ad, ad_id=ad_id, active=True)

    AdStat.objects.create(
        ad=ad,
        event="click",
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")
    )

    return Response({"ok": True})


# 🛠️ CREATE / UPDATE (ADMIN)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_or_update_ad(request):
    data = request.data
    ad_id = data.get("ad_id")

    if not ad_id:
        return Response({"detail": "ad_id required"}, status=status.HTTP_400_BAD_REQUEST)

    ad, _ = Ad.objects.update_or_create(
        ad_id=ad_id,
        defaults={
            "title": data.get("title"),
            "image": data.get("image"),
            "video": data.get("video"),
            "link": data.get("link"),
            "page": data.get("page"),
            "position": data.get("position", "top"),
            "competition_id": data.get("competition_id"),
            "match_id": data.get("match_id"),
            "club_id": data.get("club_id"),
            "priority": data.get("priority", 1),
            "active": data.get("active", True),
        }
    )

    return Response(AdSerializer(ad, context={"request": request}).data)


# 📈 STATS
@api_view(["GET"])
def get_stats(request):
    ad_id = request.query_params.get("ad_id")

    if not ad_id:
        return Response({"detail": "ad_id required"}, status=status.HTTP_400_BAD_REQUEST)

    ad = get_object_or_404(Ad, ad_id=ad_id)

    total = AdStat.objects.filter(ad=ad).values("event").annotate(count=Count("id"))
    totals = {row["event"]: row["count"] for row in total}

    res = {
        "ad_id": ad.ad_id,
        "title": ad.title,
        "totals": {
            "impression": totals.get("impression", 0),
            "click": totals.get("click", 0)
        }
    }

    group = request.query_params.get("group_by")

    if group == "day":
        daily = (
            AdStat.objects
            .filter(ad=ad)
            .annotate(day=TruncDate("created_at"))
            .values("day", "event")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        out = {}
        for row in daily:
            d = row["day"].isoformat()
            out.setdefault(d, {"impression": 0, "click": 0})
            out[d][row["event"]] = row["count"]

        res["by_day"] = out

    return Response(res)