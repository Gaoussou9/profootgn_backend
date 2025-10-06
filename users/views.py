
from rest_framework import viewsets, permissions
from .models import Profile
from .serializers import ProfileSerializer

class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.select_related('user','favorite_club').all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.AllowAny]
