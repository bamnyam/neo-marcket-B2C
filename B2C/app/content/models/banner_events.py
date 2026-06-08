import uuid

from django.conf import settings
from django.db import models

from app.content.models.banners import Banner


class BannerEventType(models.TextChoices):
    IMPRESSION = "impression", "Impression"
    CLICK = "click", "Click"


class BannerEvent(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    banner = models.ForeignKey(
        Banner,
        on_delete=models.CASCADE,
        related_name="events",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="banner_events",
        null=True,
        blank=True,
    )
    event = models.CharField(
        max_length=20,
        choices=BannerEventType.choices,
    )
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["banner", "event"]),
            models.Index(fields=["timestamp"]),
        ]
