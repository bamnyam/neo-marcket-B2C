import uuid

from django.db import models

from app.orders.models.order_status import OrderStatus
from app.orders.models.orders import Order


class OrderStatusHistory(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    status_from = models.CharField(
        max_length=50,
        choices=OrderStatus.choices,
        null=True,
        blank=True,
    )
    status_to = models.CharField(
        max_length=50,
        choices=OrderStatus.choices,
    )
    reason = models.CharField(
        max_length=500,
        blank=True,
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["order", "changed_at"]),
        ]
