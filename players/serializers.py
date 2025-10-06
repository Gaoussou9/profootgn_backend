
from rest_framework import serializers
from .models import Player

class PlayerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = ['id','first_name','last_name','full_name','club','number','position','nationality','birthdate','photo']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
