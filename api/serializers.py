from rest_framework import serializers
from .models import UserModel

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = UserModel
        fields = ['id', 'email', 'first_name', 'last_name', 'user_type', 'password']

    def create(self, validated_data):
        user = UserModel(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            user_type=validated_data['user_type']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user
