from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from cats.models import Cat
from .models import Handover, CareTask, Completion, Incident, HandoverEvent


class HandoverSerializer(serializers.ModelSerializer):
    sitter = serializers.SlugRelatedField(
        slug_field="username", queryset=get_user_model().objects.filter(is_active=True)
    )

    class Meta:
        model = Handover
        fields = [
            "id",
            "cat",
            "owner",
            "sitter",
            "starts_at",
            "ends_at",
            "instructions",
            "status",
            "created_at",
        ]
        read_only_fields = ["owner", "status", "created_at"]

    def validate(self, data):
        user = self.context["request"].user
        if data["cat"].owner_id != user.id:
            raise serializers.ValidationError(
                {"cat": "Можно передать уход только за своим котом."}
            )
        if data["sitter"] == user:
            raise serializers.ValidationError(
                {"sitter": "Помощник должен отличаться от владельца."}
            )
        if data["ends_at"] <= data["starts_at"]:
            raise serializers.ValidationError(
                {"ends_at": "Конец должен быть позже начала."}
            )
        if data["ends_at"] <= timezone.now():
            raise serializers.ValidationError(
                {"ends_at": "Нельзя создать уже завершившуюся смену."}
            )
        return data


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareTask
        fields = [
            "id",
            "handover",
            "title",
            "instructions",
            "due_at",
            "required",
            "photo_required",
        ]


class CompletionSerializer(serializers.ModelSerializer):
    evidence_url = serializers.SerializerMethodField()

    class Meta:
        model = Completion
        # Duplicate checks run after visibility and state checks under the parent lock.
        validators = []
        fields = [
            "id",
            "task",
            "author",
            "note",
            "evidence",
            "evidence_url",
            "status",
            "review_note",
            "created_at",
            "reviewed_at",
        ]
        read_only_fields = [
            "author",
            "status",
            "review_note",
            "created_at",
            "reviewed_at",
        ]
        extra_kwargs = {"evidence": {"write_only": True}}

    def get_evidence_url(self, obj) -> str | None:
        if obj.evidence:
            return self.context["request"].build_absolute_uri(
                f"/api/completions/{obj.pk}/evidence/"
            )
        return None

    def validate_evidence(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Фото не более 5 МБ.")
        return value


class ReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "rejected"])
    note = serializers.CharField(
        max_length=2000, allow_blank=True, required=False, default=""
    )

    def validate(self, data):
        if data["decision"] == "rejected" and not data["note"].strip():
            raise serializers.ValidationError({"note": "Укажите причину возврата."})
        return data


class ResolutionSerializer(serializers.Serializer):
    resolution = serializers.CharField(max_length=3000)


class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = [
            "id",
            "handover",
            "author",
            "severity",
            "description",
            "resolution",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = ["author", "resolution", "resolved_at", "created_at"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverEvent
        fields = ["id", "actor", "kind", "detail", "created_at"]


class ReportSerializer(serializers.Serializer):
    handover = serializers.IntegerField()
    status = serializers.CharField()
    tasks_total = serializers.IntegerField()
    required_total = serializers.IntegerField()
    approved_required = serializers.IntegerField()
    overdue = serializers.IntegerField()
    pending_reviews = serializers.IntegerField()
    unresolved_incidents = serializers.IntegerField()
    can_close = serializers.BooleanField()


class ExtendSerializer(serializers.Serializer):
    ends_at = serializers.DateTimeField()
    reason = serializers.CharField(max_length=2000)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)
