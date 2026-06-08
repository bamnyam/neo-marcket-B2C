import uuid

from django.conf import settings
from django.db import models

from app.orders.models.order_status import OrderStatus


class Order(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=50,
        choices=OrderStatus.choices,
        default=OrderStatus.CREATED,
        db_index=True,
    )
    idempotency_key = models.UUIDField(
        unique=True,
        db_index=True,
    )
    total_amount = models.PositiveBigIntegerField(default=0)
    delivery_address = models.TextField(
        null=True,
        blank=True,
    )
    cancel_reason = models.CharField(
        max_length=500,
        blank=True,
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["buyer", "status", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
