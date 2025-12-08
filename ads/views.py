from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Count
from .models import Ad, AdStat
from .serializers import AdSerializer

@api_view(["GET"])
def list_ads(request):
    ads = Ad.objects.filter(active=True)
    serializer = AdSerializer(ads, many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([AllowAny])
def log_impression(request):
    ad_id = request.data.get("ad_id")
    if not ad_id:
        return Response({"detail":"ad_id required"}, status=status.HTTP_400_BAD_REQUEST)
    ad = get_object_or_404(Ad, ad_id=ad_id, active=True)
    AdStat.objects.create(
        ad=ad,
        event="impression",
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT","")
    )
    return Response({"ok": True})

@api_view(["POST"])
@permission_classes([AllowAny])
def log_click(request):
    ad_id = request.data.get("ad_id")
    if not ad_id:
        return Response({"detail":"ad_id required"}, status=status.HTTP_400_BAD_REQUEST)
    ad = get_object_or_404(Ad, ad_id=ad_id, active=True)
    AdStat.objects.create(
        ad=ad,
        event="click",
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT","")
    )
    return Response({"ok": True})

@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_or_update_ad(request):
    data = request.data
    ad_id = data.get("ad_id")
    if not ad_id:
        return Response({"detail":"ad_id required"}, status=status.HTTP_400_BAD_REQUEST)
    ad, _ = Ad.objects.update_or_create(ad_id=ad_id, defaults={
        "title": data.get("title"),
        "image": data.get("image"),
        "video": data.get("video"),
        "link": data.get("link"),
        "active": data.get("active", True)
    })
    return Response(AdSerializer(ad).data)

@api_view(["GET"])
def get_stats(request):
    """
    GET /api/ads/stats/?ad_id=silkcoat-home-1&group_by=day
    returns total impressions & clicks and (optional) grouped counts by day.
    """
    ad_id = request.query_params.get("ad_id")
    if not ad_id:
        return Response({"detail":"ad_id required"}, status=status.HTTP_400_BAD_REQUEST)
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
        # counts per day (YYYY-MM-DD)
        from django.db.models.functions import TruncDate
        daily = AdStat.objects.filter(ad=ad).annotate(day=TruncDate("created_at")).values("day","event").annotate(count=Count("id")).order_by("day")
        # structure: { "2025-12-01": {impression: X, click: Y}, ... }
        out = {}
        for row in daily:
            d = row["day"].isoformat()
            out.setdefault(d, {"impression":0,"click":0})
            out[d][row["event"]] = row["count"]
        res["by_day"] = out

    return Response(res)
