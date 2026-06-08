import uuid

from django.conf import settings
from django.db import models


class PaymentMethodType(models.TextChoices):
    CARD = "CARD", "Card"
    SBP = "SBP", "SBP"
    WALLET = "WALLET", "Wallet"


class PaymentMethod(models.Model):
    class CardBrand(models.TextChoices):
        VISA = "VISA", "Visa"
        MASTERCARD = "MASTERCARD", "Mastercard"
        MIR = "MIR", "Mir"

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_methods",
    )
    type = models.CharField(
        max_length=20,
        choices=PaymentMethodType.choices,
    )
    card_last4 = models.CharField(
        max_length=4,
        blank=True,
    )
    card_brand = models.CharField(
        max_length=20,
        choices=CardBrand.choices,
        blank=True,
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
