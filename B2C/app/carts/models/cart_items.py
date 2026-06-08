import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class UnavailableReason(models.TextChoices):
    OUT_OF_STOCK = "OUT_OF_STOCK", "Out of stock"
    PRODUCT_BLOCKED = "PRODUCT_BLOCKED", "Product blocked"
    PRODUCT_DELETED = "PRODUCT_DELETED", "Product deleted"
    PRODUCT_DELISTED = "PRODUCT_DELISTED", "Product delisted"
    ON_MODERATION = "ON_MODERATION", "On moderation"


class CartItem(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cart_items",
        null=True,
        blank=True,
    )
    session_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )
    sku_id = models.UUIDField(db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price_at_add = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )
    available = models.BooleanField(default=True)
    unavailable_reason = models.CharField(
        max_length=50,
        choices=UnavailableReason.choices,
        null=True,
        blank=True,
    )
    unavailable_message = models.CharField(
        max_length=255,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, session_id__isnull=True)
                    | Q(user__isnull=True, session_id__isnull=False)
                ),
                name="cart_item_exactly_one_identity",
            ),
            models.UniqueConstraint(
                fields=["user", "sku_id"],
                condition=Q(user__isnull=False),
                name="unique_user_cart_sku",
            ),
            models.UniqueConstraint(
                fields=["session_id", "sku_id"],
                condition=Q(session_id__isnull=False),
                name="unique_session_cart_sku",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "sku_id"]),
            models.Index(fields=["session_id", "sku_id"]),
        ]
