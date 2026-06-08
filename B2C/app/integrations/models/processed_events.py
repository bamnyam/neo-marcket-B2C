import uuid

from django.db import models


class SenderService(models.TextChoices):
    B2B = "b2b", "B2B"
    MODERATION = "moderation", "Moderation"
    B2C = "b2c", "B2C"


class ProcessedEvent(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    sender_service = models.CharField(
        max_length=20,
        choices=SenderService.choices,
    )
    idempotency_key = models.UUIDField()
    response_cached = models.JSONField(
        null=True,
        blank=True,
    )
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sender_service", "idempotency_key"],
                name="unique_processed_event_sender_key",
            ),
        ]
        indexes = [
            models.Index(fields=["processed_at"]),
        ]
