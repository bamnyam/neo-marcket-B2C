import uuid

from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED", "Order status changed"
    BACK_IN_STOCK = "BACK_IN_STOCK", "Back in stock"
    PRICE_DROP = "PRICE_DROP", "Price drop"
    PROMO = "PROMO", "Promo"
    SYSTEM = "SYSTEM", "System"


class Notification(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["buyer", "is_read", "created_at"]),
            models.Index(fields=["type"]),
        ]
