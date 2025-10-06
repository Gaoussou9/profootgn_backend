# clubs/views.py
from rest_framework import viewsets, permissions, filters
from .models import Club, StaffMember
from .serializers import ClubSerializer, StaffSerializer

class ClubViewSet(viewsets.ModelViewSet):
    """
    - GET /api/clubs/           → liste (public)
    - GET /api/clubs/{id}/      → détail (public)
    - POST/PUT/PATCH/DELETE     → admin authentifié
    """
    queryset = Club.objects.all().order_by("name")
    serializer_class = ClubSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        city = self.request.query_params.get("city")
        if q:
            qs = qs.filter(name__icontains=q)
        if city:
            qs = qs.filter(city__icontains=city)
        return qs


class StaffMemberViewSet(viewsets.ModelViewSet):
    """
    - GET /api/staff/?club=7[,8] [&active=1] [&ordering=full_name] → public
    - GET /api/staff/{id}/      → public
    - POST/PUT/PATCH/DELETE     → admin authentifié
    """
    queryset = StaffMember.objects.select_related("club").all()
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), permissions.IsAdminUser()]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    # 🔎 champs qui existent vraiment
    search_fields = ["full_name", "role", "email", "phone", "club__name"]
    ordering_fields = ["full_name", "role", "id"]
    ordering = ["full_name", "id"]

    def get_queryset(self):
        qs = super().get_queryset()

        # ?club=7 ou ?club=7,8,9 (alias ?club_id=…)
        raw = self.request.query_params.get("club") or self.request.query_params.get("club_id")
        if raw:
            ids = [s.strip() for s in str(raw).split(",") if s.strip().isdigit()]
            if ids:
                qs = qs.filter(club_id__in=ids)

        # ?active=1 → n’afficher que les actifs
        active = self.request.query_params.get("active")
        if active in {"1", "true", "True"}:
            qs = qs.filter(is_active=True)

        return qs
