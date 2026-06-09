from django.db import IntegrityError, transaction
from django.utils import timezone

from app.orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.orders.services.b2b_client import (
    B2BOrdersClient,
    ReserveFailedError,
)


class CheckoutService:
    def __init__(self, b2b_client=None):
        self.b2b_client = b2b_client or B2BOrdersClient()

    def checkout(self, buyer, idempotency_key, items, delivery_address=None):
        existing = self._existing_order(buyer, idempotency_key)

        if existing is not None:
            return existing, False

        sku_map = self.b2b_client.get_skus([item["sku_id"] for item in items])
        failed_items = self._validate_items(items, sku_map)

        if failed_items:
            raise ReserveFailedError(failed_items)

        self.b2b_client.reserve(idempotency_key, items)

        try:
            with transaction.atomic():
                existing = self._existing_order(buyer, idempotency_key, lock=True)

                if existing is not None:
                    return existing, False

                order = Order.objects.create(
                    buyer=buyer,
                    status=OrderStatus.CREATED,
                    idempotency_key=idempotency_key,
                    delivery_address=delivery_address or "",
                    total_amount=self._total_amount(items, sku_map),
                )
                self._create_items(order, items, sku_map)
                self._mark_paid(order)
                return order, True
        except IntegrityError:
            return self._existing_order(buyer, idempotency_key), False

    def _existing_order(self, buyer, idempotency_key, lock=False):
        queryset = Order.objects.prefetch_related("items")

        if lock:
            queryset = queryset.select_for_update()

        return queryset.filter(buyer=buyer, idempotency_key=idempotency_key).first()

    def _validate_items(self, items, sku_map):
        failed_items = []

        for item in items:
            sku_id = str(item["sku_id"])
            sku = sku_map.get(sku_id)

            if sku is None:
                failed_items.append(
                    {
                        "sku_id": sku_id,
                        "requested": item["quantity"],
                        "available": 0,
                        "reason": "SKU_NOT_FOUND",
                    }
                )
                continue

            reason = self._unavailable_reason(sku, item["quantity"])

            if reason is not None:
                failed_items.append(
                    {
                        "sku_id": sku_id,
                        "requested": item["quantity"],
                        "available": sku["available_quantity"],
                        "reason": reason,
                    }
                )

        return failed_items

    def _unavailable_reason(self, sku, requested):
        if sku["product_deleted"]:
            return "PRODUCT_DELETED"

        if sku["product_status"] in {"BLOCKED", "HARD_BLOCKED"}:
            return "PRODUCT_BLOCKED"

        if sku["available_quantity"] <= 0:
            return "OUT_OF_STOCK"

        if sku["available_quantity"] < requested:
            return "INSUFFICIENT_STOCK"

        return None

    def _total_amount(self, items, sku_map):
        return sum(
            self._unit_price(sku_map[str(item["sku_id"])]) * item["quantity"]
            for item in items
        )

    def _create_items(self, order, items, sku_map):
        order_items = []

        for item in items:
            sku = sku_map[str(item["sku_id"])]
            unit_price = self._unit_price(sku)
            order_items.append(
                OrderItem(
                    order=order,
                    sku_id=item["sku_id"],
                    product_id=sku["product_id"],
                    product_title=sku["product_title"],
                    sku_name=sku["sku_name"],
                    quantity=item["quantity"],
                    unit_price=unit_price,
                    line_total=unit_price * item["quantity"],
                )
            )

        OrderItem.objects.bulk_create(order_items)

    def _mark_paid(self, order):
        OrderStatusHistory.objects.create(
            order=order,
            status_from=None,
            status_to=OrderStatus.CREATED,
            reason="checkout_created",
        )
        order.status = OrderStatus.PAID
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "paid_at", "updated_at"])
        OrderStatusHistory.objects.create(
            order=order,
            status_from=OrderStatus.CREATED,
            status_to=OrderStatus.PAID,
            reason="mock_payment_success",
        )

    def _unit_price(self, sku):
        return max(sku["price"] - sku["discount"], 0)
