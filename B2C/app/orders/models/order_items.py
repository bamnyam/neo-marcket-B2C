import uuid

from django.db import models

from app.orders.models.orders import Order


class OrderItem(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    sku_id = models.UUIDField(db_index=True)
    product_id = models.UUIDField(db_index=True)
    product_title = models.CharField(max_length=255)
    sku_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveBigIntegerField()
    line_total = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["order", "sku_id"]),
            models.Index(fields=["product_id"]),
        ]
