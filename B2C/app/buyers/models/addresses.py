import uuid

from django.conf import settings
from django.db import models


class Address(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="addresses",
    )
    country = models.CharField(max_length=100)
    region = models.CharField(
        max_length=200,
        blank=True,
    )
    city = models.CharField(max_length=200)
    street = models.CharField(max_length=200)
    building = models.CharField(max_length=50)
    apartment = models.CharField(
        max_length=50,
        blank=True,
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
    )
    recipient_name = models.CharField(
        max_length=200,
        blank=True,
    )
    recipient_phone = models.CharField(
        max_length=20,
        blank=True,
    )
    is_default = models.BooleanField(default=False)
    comment = models.CharField(
        max_length=500,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
