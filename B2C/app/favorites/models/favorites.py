import uuid

from django.conf import settings
from django.db import models


class Favorite(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="favorites",
    )
    product_id = models.UUIDField(db_index=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "product_id"],
                name="unique_buyer_favorite_product",
            ),
        ]
        indexes = [
            models.Index(fields=["buyer", "product_id"]),
        ]
