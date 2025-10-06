
from rest_framework import serializers
from .models import Recruiter, TrialRequest

class RecruiterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recruiter
        fields = '__all__'

class TrialRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrialRequest
        fields = '__all__'
