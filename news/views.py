
from rest_framework import viewsets, filters
from .models import NewsItem
from .serializers import NewsItemSerializer

class NewsItemViewSet(viewsets.ModelViewSet):
    queryset = NewsItem.objects.select_related('club').all()
    serializer_class = NewsItemSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title','content','club__name']
    ordering_fields = ['published_at','title']
    ordering = ['-published_at']
