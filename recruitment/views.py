
from rest_framework import viewsets
from .models import Recruiter, TrialRequest
from .serializers import RecruiterSerializer, TrialRequestSerializer

class RecruiterViewSet(viewsets.ModelViewSet):
    queryset = Recruiter.objects.all()
    serializer_class = RecruiterSerializer

class TrialRequestViewSet(viewsets.ModelViewSet):
    queryset = TrialRequest.objects.select_related('player','recruiter').all()
    serializer_class = TrialRequestSerializer
