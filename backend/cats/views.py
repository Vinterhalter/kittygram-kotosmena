from django.db.models.deletion import ProtectedError
from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from .models import Cat, Achievement
from .serializers import CatSerializer, AchievementSerializer
from .permissions import OwnerOrReadOnly


class CatViewSet(viewsets.ModelViewSet):
    queryset = (
        Cat.objects.select_related("owner").prefetch_related("achievements").all()
    )
    serializer_class = CatSerializer
    permission_classes = [IsAuthenticated, OwnerOrReadOnly]
    filterset_fields = ["owner", "color", "birth_year"]
    search_fields = ["name"]
    ordering_fields = ["id", "name", "birth_year"]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                "Кот связан со сменами ухода. Удаление запрещено для сохранения истории."
            )


class AchievementViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer
    search_fields = ["name"]
