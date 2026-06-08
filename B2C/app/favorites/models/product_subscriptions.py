import uuid

from django.conf import settings
from django.db import models


class ProductSubscriptionEvent(models.TextChoices):
    IN_STOCK = "IN_STOCK", "In stock"
    PRICE_DOWN = "PRICE_DOWN", "Price down"


class ProductSubscription(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_subscriptions",
    )
    product_id = models.UUIDField(db_index=True)
    notify_on = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "product_id"],
                name="unique_buyer_product_subscription",
            ),
        ]
        indexes = [
            models.Index(fields=["buyer", "product_id"]),
        ]
