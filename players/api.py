from rest_framework import viewsets, filters
from .models import Player
from .serializers import PlayerSerializer

class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.select_related('club').all()
    serializer_class = PlayerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name','last_name','nationality','club__name']
    ordering_fields = ['last_name','number']
    ordering = ['last_name']

    # ✅ filtre par ?club=<id> pour ne retourner que les joueurs du club choisi
    def get_queryset(self):
        qs = super().get_queryset()
        club = self.request.query_params.get("club")
        if club:
            qs = qs.filter(club_id=club)
        return qs
