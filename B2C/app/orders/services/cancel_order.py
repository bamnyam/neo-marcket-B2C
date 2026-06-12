import logging

from django.db import transaction

from app.orders.models import Order, OrderStatus, OrderStatusHistory
from app.orders.services.b2b_client import B2BOrdersClient, B2BUnavailableError

logger = logging.getLogger(__name__)


class OrderNotFoundError(Exception):
    pass


class CancelNotAllowedError(Exception):
    def __init__(self, current_status):
        self.current_status = current_status
        super().__init__("Order cannot be cancelled")


class CancelOrderService:
    cancellable_statuses = {
        OrderStatus.CREATED,
        OrderStatus.PAID,
        OrderStatus.ASSEMBLING,
        OrderStatus.DELIVERING
    }

    def __init__(self, b2b_client=None):
        self.b2b_client = b2b_client or B2BOrdersClient()

    def cancel(self, buyer, order_id, reason=""):
        with transaction.atomic():
            order = self._get_order_for_update(buyer, order_id)

            if order.status not in self.cancellable_statuses:
                raise CancelNotAllowedError(order.status)

            items = self._unreserve_items(order)

            try:
                self.b2b_client.unreserve(order.uuid, items)
            except B2BUnavailableError:
                logger.exception(
                    "B2B unreserve failed for order %s; cancellation is pending",
                    order.uuid,
                )
                self._transition(
                    order,
                    OrderStatus.CANCEL_PENDING,
                    "cancel_unreserve_pending",
                    reason,
                )
                return order

            self._transition(
                order,
                OrderStatus.CANCELLED,
                "cancel_unreserve_success",
                reason,
            )
            return order

    def _get_order_for_update(self, buyer, order_id):
        order = (
            Order.objects.select_for_update()
            .select_related("buyer")
            .prefetch_related("items")
            .filter(buyer=buyer, uuid=order_id)
            .first()
        )

        if order is None:
            raise OrderNotFoundError

        return order

    def _unreserve_items(self, order):
        return [
            {
                "sku_id": item.sku_id,
                "quantity": item.quantity,
            }
            for item in order.items.all()
        ]

    def _transition(self, order, status, history_reason, cancel_reason=""):
        old_status = order.status
        order.status = status

        update_fields = ["status", "updated_at"]
        if cancel_reason:
            order.cancel_reason = cancel_reason
            update_fields.append("cancel_reason")

        order.save(update_fields=update_fields)
        OrderStatusHistory.objects.create(
            order=order,
            status_from=old_status,
            status_to=status,
            reason=history_reason,
        )


def retry_pending_cancellations(b2b_client=None):
    b2b_client = b2b_client or B2BOrdersClient()
    cancelled_count = 0

    for order in (
        Order.objects.filter(status=OrderStatus.CANCEL_PENDING)
        .select_related("buyer", "address", "payment_method")
        .prefetch_related("items")
    ):
        items = [
            {
                "sku_id": item.sku_id,
                "quantity": item.quantity,
            }
            for item in order.items.all()
        ]

        try:
            b2b_client.unreserve(order.uuid, items)
        except B2BUnavailableError:
            logger.exception("Retry unreserve failed for order %s", order.uuid)
            continue

        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(pk=order.pk)

            if locked_order.status != OrderStatus.CANCEL_PENDING:
                continue

            old_status = locked_order.status
            locked_order.status = OrderStatus.CANCELLED
            locked_order.save(update_fields=["status", "updated_at"])
            OrderStatusHistory.objects.create(
                order=locked_order,
                status_from=old_status,
                status_to=OrderStatus.CANCELLED,
                reason="cancel_unreserve_retry_success",
            )
            cancelled_count += 1

    return cancelled_count
