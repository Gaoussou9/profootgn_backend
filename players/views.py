# players/views.py
from rest_framework import viewsets, filters, permissions
from django.db.models import Q

from .models import Player
from .serializers import PlayerSerializer


class PlayerViewSet(viewsets.ModelViewSet):
    """
    /api/players/
      - ?club=<id>            → ne renvoie que les joueurs de ce club
      - ?club_id=<id>         → alias
      - ?club=<id1,id2,...>   → plusieurs clubs possibles
      - search, ordering      → voir ci-dessous
    """
    queryset = Player.objects.select_related("club").all()
    serializer_class = PlayerSerializer

    # 🔐 par défaut on protège, on ouvre seulement list/retrieve plus bas
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    # Recherche / tri existants
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "nationality", "club__name"]
    ordering_fields = ["last_name", "number"]
    ordering = ["last_name"]

    def get_permissions(self):
        # Lecture publique
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        # Écriture = admin authentifié
        return [permissions.IsAuthenticated(), permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()

        # Filtre club (supporte "7" ou "7,8,9")
        raw = self.request.query_params.get("club") or self.request.query_params.get("club_id")
        if raw:
            ids = [int(s) for s in str(raw).split(",") if s.strip().isdigit()]
            if ids:
                qs = qs.filter(club_id__in=ids)

        return qs
