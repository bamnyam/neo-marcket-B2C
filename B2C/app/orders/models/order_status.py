from django.db import models


class OrderStatus(models.TextChoices):
    CREATED = "CREATED", "Created"
    PAID = "PAID", "Paid"
    ASSEMBLING = "ASSEMBLING", "Assembling"
    DELIVERING = "DELIVERING", "Delivering"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"
    CANCEL_PENDING = "CANCEL_PENDING", "Cancel pending"
