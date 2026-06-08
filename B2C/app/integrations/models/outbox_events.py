import uuid

from django.db import models


class OutboxEventStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class OutboxEvent(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    idempotency_key = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    target_url = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=OutboxEventStatus.choices,
        default=OutboxEventStatus.PENDING,
    )
    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["event_type"]),
        ]
