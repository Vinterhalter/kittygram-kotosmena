from pathlib import Path
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from cats.models import Cat
from .models import Handover, CareTask, Completion, Incident, HandoverEvent
from .serializers import (
    HandoverSerializer,
    TaskSerializer,
    CompletionSerializer,
    ReviewSerializer,
    IncidentSerializer,
    ResolutionSerializer,
    EventSerializer,
    ReportSerializer,
    ExtendSerializer,
    CancelSerializer,
)


def visible(user):
    return Handover.objects.filter(Q(owner=user) | Q(sitter=user))


def locked_handover(user, pk):
    return get_object_or_404(visible(user).select_for_update(), pk=pk)


def owner_only(user, h):
    if h.owner_id != user.id:
        raise PermissionDenied("Действие доступно только владельцу смены.")


def require_state(h, expected):
    if h.status != expected:
        raise ValidationError({"status": f"Требуется состояние {expected}."})


def event(h, user, kind, **detail):
    HandoverEvent.objects.create(handover=h, actor=user, kind=kind, detail=detail)


def report(h):
    tasks = h.tasks.all()
    approved = tasks.filter(completions__status="approved")
    missing = (
        tasks.filter(required=True).exclude(completions__status="approved").count()
    )
    unresolved = h.incidents.filter(resolved_at__isnull=True).count()
    return {
        "handover": h.id,
        "status": h.status,
        "tasks_total": tasks.count(),
        "required_total": tasks.filter(required=True).count(),
        "approved_required": approved.filter(required=True).count(),
        "overdue": tasks.filter(due_at__lt=timezone.now())
        .exclude(completions__status="approved")
        .count(),
        "pending_reviews": Completion.objects.filter(
            task__handover=h, status="pending"
        ).count(),
        "unresolved_incidents": unresolved,
        "can_close": h.status == "active" and not missing and not unresolved,
    }


class HandoverViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = HandoverSerializer
    filterset_fields = ["status", "cat", "sitter"]
    ordering_fields = ["id", "starts_at", "ends_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Handover.objects.none()
        return visible(self.request.user).select_related("cat", "owner", "sitter")

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        # The cat row serializes overlapping-shift checks across concurrent requests.
        get_object_or_404(Cat.objects.select_for_update(), pk=data["cat"].pk)
        if Handover.objects.filter(
            cat=data["cat"],
            status__in=["draft", "active"],
            starts_at__lt=data["ends_at"],
            ends_at__gt=data["starts_at"],
        ).exists():
            raise ValidationError(
                {"cat": "Для кота уже есть пересекающаяся незакрытая смена."}
            )
        h = serializer.save(owner=self.request.user)
        event(h, self.request.user, "created")

    @extend_schema(request=None, responses=HandoverSerializer)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def accept(self, request, pk=None):
        h = locked_handover(request.user, pk)
        if request.user.id != h.sitter_id:
            raise PermissionDenied("Смену принимает назначенный помощник.")
        require_state(h, "draft")
        if h.ends_at <= timezone.now():
            raise ValidationError("Срок смены уже закончился.")
        if not h.tasks.filter(required=True).exists():
            raise ValidationError("Добавьте хотя бы одну обязательную задачу.")
        h.status = "active"
        h.save(update_fields=["status"])
        event(h, request.user, "accepted")
        return Response(self.get_serializer(h).data)

    @extend_schema(request=None, responses=HandoverSerializer)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def close(self, request, pk=None):
        h = locked_handover(request.user, pk)
        owner_only(request.user, h)
        require_state(h, "active")
        if not report(h)["can_close"]:
            raise ValidationError(
                "Нужно принять все обязательные задачи и решить все инциденты."
            )
        h.status = "closed"
        h.save(update_fields=["status"])
        event(h, request.user, "closed")
        return Response(self.get_serializer(h).data)

    @extend_schema(request=ExtendSerializer, responses=HandoverSerializer)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def extend(self, request, pk=None):
        original = self.get_object()
        get_object_or_404(Cat.objects.select_for_update(), pk=original.cat_id)
        h = locked_handover(request.user, pk)
        owner_only(request.user, h)
        if h.status not in ["draft", "active"]:
            raise ValidationError("Можно продлить только незавершённую смену.")
        s = ExtendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        end = s.validated_data["ends_at"]
        if end <= h.ends_at or end <= timezone.now():
            raise ValidationError(
                {"ends_at": "Новый срок должен быть позже прежнего и текущего времени."}
            )
        if (
            Handover.objects.filter(
                cat=h.cat,
                status__in=["draft", "active"],
                starts_at__lt=end,
                ends_at__gt=h.starts_at,
            )
            .exclude(pk=h.pk)
            .exists()
        ):
            raise ValidationError("Продление пересекается с другой сменой.")
        previous = h.ends_at.isoformat()
        h.ends_at = end
        h.save(update_fields=["ends_at"])
        event(
            h,
            request.user,
            "extended",
            previous=previous,
            ends_at=end.isoformat(),
            reason=s.validated_data["reason"],
        )
        return Response(self.get_serializer(h).data)

    @extend_schema(request=CancelSerializer, responses=HandoverSerializer)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancel(self, request, pk=None):
        h = locked_handover(request.user, pk)
        owner_only(request.user, h)
        if h.status not in ["draft", "active"]:
            raise ValidationError("Смена уже завершена.")
        s = CancelSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        h.status = "cancelled"
        h.save(update_fields=["status"])
        event(h, request.user, "cancelled", reason=s.validated_data["reason"])
        return Response(self.get_serializer(h).data)

    @extend_schema(responses=ReportSerializer)
    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        return Response(report(self.get_object()))

    @extend_schema(responses=EventSerializer(many=True))
    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        events = self.get_object().events.all()
        page = self.paginate_queryset(events)
        return self.get_paginated_response(EventSerializer(page, many=True).data)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    filterset_fields = ["handover", "required", "photo_required"]
    search_fields = ["title"]
    ordering_fields = ["id", "due_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CareTask.objects.none()
        return CareTask.objects.filter(
            handover__in=visible(self.request.user)
        ).select_related("handover")

    def _save_task(self, serializer):
        old = serializer.instance
        handover_id = (
            old.handover_id if old else serializer.validated_data["handover"].pk
        )
        h = locked_handover(self.request.user, handover_id)
        owner_only(self.request.user, h)
        require_state(h, "draft")
        if (
            old
            and "handover" in serializer.validated_data
            and serializer.validated_data["handover"].pk != h.pk
        ):
            raise ValidationError(
                {"handover": "Перенос задачи в другую смену запрещён."}
            )
        due = serializer.validated_data.get("due_at", old.due_at if old else None)
        if not h.starts_at <= due <= h.ends_at:
            raise ValidationError(
                {"due_at": "Срок задачи должен находиться внутри смены."}
            )
        obj = serializer.save()
        event(
            h, self.request.user, "task_updated" if old else "task_created", task=obj.pk
        )

    @transaction.atomic
    def perform_create(self, serializer):
        self._save_task(serializer)

    @transaction.atomic
    def perform_update(self, serializer):
        self._save_task(serializer)

    @transaction.atomic
    def perform_destroy(self, instance):
        h = locked_handover(self.request.user, instance.handover_id)
        owner_only(self.request.user, h)
        require_state(h, "draft")
        task_id = instance.pk
        instance.delete()
        event(h, self.request.user, "task_deleted", task=task_id)

    @extend_schema(responses=TaskSerializer(many=True))
    @action(detail=False, methods=["get"])
    def overdue(self, request):
        qs = (
            self.filter_queryset(self.get_queryset())
            .filter(handover__status="active", due_at__lt=timezone.now())
            .exclude(completions__status="approved")
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class CompletionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CompletionSerializer
    filterset_fields = ["task", "status"]
    ordering_fields = ["id", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Completion.objects.none()
        return Completion.objects.filter(
            task__handover__in=visible(self.request.user)
        ).select_related("task__handover")

    @transaction.atomic
    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        h = locked_handover(self.request.user, task.handover_id)
        if h.sitter_id != self.request.user.id:
            raise PermissionDenied("Результат отправляет назначенный помощник.")
        require_state(h, "active")
        if not h.starts_at <= timezone.now() <= h.ends_at:
            raise ValidationError("Результат можно отправить только в период смены.")
        if task.photo_required and not serializer.validated_data.get("evidence"):
            raise ValidationError({"evidence": "Для этой задачи обязательно фото."})
        if task.completions.filter(status__in=["pending", "approved"]).exists():
            raise ValidationError(
                {
                    "task": "У задачи уже есть результат на проверке или принятый результат."
                }
            )
        obj = serializer.save(author=self.request.user)
        event(h, self.request.user, "submitted", completion=obj.pk, task=task.pk)

    @extend_schema(request=ReviewSerializer, responses=CompletionSerializer)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def review(self, request, pk=None):
        obj = self.get_object()
        h = locked_handover(request.user, obj.task.handover_id)
        owner_only(request.user, h)
        require_state(h, "active")
        obj.refresh_from_db()
        if obj.status != "pending":
            raise ValidationError("Этот результат уже проверен.")
        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        obj.status = s.validated_data["decision"]
        obj.review_note = s.validated_data["note"]
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=["status", "review_note", "reviewed_at"])
        event(h, request.user, "reviewed", completion=obj.pk, decision=obj.status)
        return Response(self.get_serializer(obj).data)

    @extend_schema(
        responses={(200, "image/jpeg"): {"type": "string", "format": "binary"}}
    )
    @action(detail=True, methods=["get"])
    def evidence(self, request, pk=None):
        obj = self.get_object()
        if not obj.evidence:
            raise NotFound("Фото отсутствует.")
        return FileResponse(
            obj.evidence.open("rb"),
            as_attachment=True,
            filename="evidence" + Path(obj.evidence.name).suffix,
        )


class IncidentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = IncidentSerializer
    filterset_fields = ["handover", "severity"]
    ordering_fields = ["id", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Incident.objects.none()
        return Incident.objects.filter(
            handover__in=visible(self.request.user)
        ).select_related("handover")

    @transaction.atomic
    def perform_create(self, serializer):
        h = locked_handover(self.request.user, serializer.validated_data["handover"].pk)
        require_state(h, "active")
        obj = serializer.save(author=self.request.user)
        event(h, self.request.user, "incident_created", incident=obj.pk)

    @extend_schema(request=ResolutionSerializer, responses=IncidentSerializer)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def resolve(self, request, pk=None):
        obj = self.get_object()
        h = locked_handover(request.user, obj.handover_id)
        owner_only(request.user, h)
        require_state(h, "active")
        obj.refresh_from_db()
        if obj.resolved_at:
            raise ValidationError("Инцидент уже решён.")
        s = ResolutionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        obj.resolution = s.validated_data["resolution"]
        obj.resolved_at = timezone.now()
        obj.save(update_fields=["resolution", "resolved_at"])
        event(h, request.user, "incident_resolved", incident=obj.pk)
        return Response(self.get_serializer(obj).data)
