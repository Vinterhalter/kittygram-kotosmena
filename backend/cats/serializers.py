from django.utils import timezone
from rest_framework import serializers
from .models import Cat, Achievement


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ["id", "name"]


class CatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cat
        fields = ["id", "owner", "name", "color", "birth_year", "image", "achievements"]
        read_only_fields = ["owner"]

    def validate_birth_year(self, value):
        if not 1900 <= value <= timezone.now().year:
            raise serializers.ValidationError(
                "Год рождения должен быть между 1900 и текущим годом."
            )
        return value

    def validate_image(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Размер фотографии не более 5 МБ.")
        return value
