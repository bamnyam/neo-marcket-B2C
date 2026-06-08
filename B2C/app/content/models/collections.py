import uuid

from django.db import models


class Collection(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(
        blank=True,
    )
    cover_image_url = models.URLField(
        max_length=500,
        blank=True,
    )
    target_url = models.CharField(
        max_length=500,
        blank=True,
    )
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "priority"]),
            models.Index(fields=["start_date"]),
        ]
