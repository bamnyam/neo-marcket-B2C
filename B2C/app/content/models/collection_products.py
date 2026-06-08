import uuid

from django.db import models

from app.content.models.collections import Collection


class CollectionProduct(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="products",
    )
    product_id = models.UUIDField(db_index=True)
    ordering = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "product_id"],
                name="unique_collection_product",
            ),
        ]
        indexes = [
            models.Index(fields=["collection", "ordering"]),
        ]
