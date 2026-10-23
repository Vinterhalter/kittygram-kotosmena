from django.conf import settings
from .storage import PrivateEvidenceStorage
from django.db import models
from django.db.models import Q, F

private_storage = PrivateEvidenceStorage()


class Handover(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Ожидает принятия"
        ACTIVE = "active", "В работе"
        CLOSED = "closed", "Закрыта"
        CANCELLED = "cancelled", "Отменена"

    cat = models.ForeignKey(
        "cats.Cat", on_delete=models.PROTECT, related_name="handovers"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_handovers",
    )
    sitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_handovers",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    instructions = models.TextField(max_length=3000, blank=True)
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="valid_handover_period"
            ),
            models.CheckConstraint(
                condition=~Q(owner=F("sitter")), name="different_care_participants"
            ),
        ]


class CareTask(models.Model):
    handover = models.ForeignKey(
        Handover, on_delete=models.PROTECT, related_name="tasks"
    )
    title = models.CharField(max_length=160)
    instructions = models.TextField(max_length=2000, blank=True)
    due_at = models.DateTimeField()
    required = models.BooleanField(default=True)
    photo_required = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_at", "id"]


class Completion(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Принято"
        REJECTED = "rejected", "На доработке"

    task = models.ForeignKey(
        CareTask, on_delete=models.PROTECT, related_name="completions"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField(max_length=2000)
    evidence = models.ImageField(
        storage=private_storage, upload_to="evidence/%Y/%m/", blank=True
    )
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.PENDING
    )
    review_note = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["task"],
                condition=Q(status__in=["pending", "approved"]),
                name="one_live_completion",
            )
        ]


class Incident(models.Model):
    handover = models.ForeignKey(
        Handover, on_delete=models.PROTECT, related_name="incidents"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    severity = models.CharField(
        max_length=8, choices=[("normal", "Обычный"), ("urgent", "Срочный")]
    )
    description = models.TextField(max_length=3000)
    resolution = models.TextField(max_length=3000, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class HandoverEvent(models.Model):
    handover = models.ForeignKey(
        Handover, on_delete=models.PROTECT, related_name="events"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
