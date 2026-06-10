import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.orders.api.serializers import CheckoutSerializer
from app.orders.services import (
    B2BUnavailableError,
    CancelNotAllowedError,
    CancelOrderService,
    CheckoutService,
    OrderNotFoundError,
    ReserveFailedError,
)


class OrdersController(APIView):
    permission_classes = [IsAuthenticated]
    service_class = CheckoutService

    def post(self, request):
        idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY")

        if not idempotency_key:
            return self._error(
                "INVALID_REQUEST",
                "Заголовок Idempotency-Key обязателен",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            idempotency_key = uuid.UUID(idempotency_key)
        except ValueError:
            return self._error(
                "INVALID_REQUEST",
                "Заголовок Idempotency-Key должен быть UUID",
                status.HTTP_400_BAD_REQUEST,
            )

        serializer = CheckoutSerializer(
            data=request.data,
            context={"buyer": request.user},
        )

        if not serializer.is_valid():
            if self._items_are_empty(serializer.errors):
                return self._error(
                    "INVALID_REQUEST",
                    "Список items не может быть пустым",
                    status.HTTP_400_BAD_REQUEST,
                )

            if self._has_quantity_error(serializer.errors):
                return self._error(
                    "INVALID_QUANTITY",
                    "Количество должно быть не менее 1 для каждой позиции",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            return self._error(
                "INVALID_REQUEST",
                "Некорректный запрос",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            order, _ = self.service_class().checkout(
                buyer=request.user,
                idempotency_key=idempotency_key,
                items=serializer.validated_data["items"],
                address=serializer.validated_data["address"],
                payment_method=serializer.validated_data["payment_method"],
                comment=serializer.validated_data.get("comment") or "",
            )
        except ReserveFailedError as exc:
            return Response(
                {
                    "code": "RESERVE_FAILED",
                    "message": "Не удалось зарезервировать товары",
                    "failed_items": exc.failed_items,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except B2BUnavailableError:
            return self._error(
                "B2B_UNAVAILABLE",
                "Сервис товаров временно недоступен, попробуйте позже",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(self._serialize_order(order), status=status.HTTP_201_CREATED)

    def _serialize_order(self, order):
        return serialize_order(order)

    def _serialize_address(self, address):
        return serialize_address(address)

    def _serialize_payment_method(self, payment_method):
        return serialize_payment_method(payment_method)

    def _error(self, code, message, response_status):
        return error_response(code, message, response_status)

    def _items_are_empty(self, errors):
        item_errors = errors.get("items")

        if not isinstance(item_errors, list) or not item_errors:
            return False

        return not isinstance(item_errors[0], dict)

    def _has_quantity_error(self, errors):
        item_errors = errors.get("items")

        if not isinstance(item_errors, list):
            return False

        return any(
            isinstance(item_error, dict) and "quantity" in item_error
            for item_error in item_errors
        )


class OrderCancelController(APIView):
    permission_classes = [IsAuthenticated]
    service_class = CancelOrderService

    def post(self, request, order_id):
        reason = ""

        if isinstance(request.data, dict):
            reason = request.data.get("reason") or ""

        if len(reason) > 500:
            return error_response(
                "INVALID_REQUEST",
                "Причина отмены не должна превышать 500 символов",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = self.service_class().cancel(
                buyer=request.user,
                order_id=order_id,
                reason=reason,
            )
        except OrderNotFoundError:
            return error_response(
                "ORDER_NOT_FOUND",
                "Заказ не найден",
                status.HTTP_404_NOT_FOUND,
            )
        except CancelNotAllowedError as exc:
            return Response(
                {
                    "code": "CANCEL_NOT_ALLOWED",
                    "message": (
                        "Отмена невозможна: заказ в статусе "
                        f"{exc.current_status}"
                    ),
                    "current_status": exc.current_status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(serialize_order(order), status=status.HTTP_200_OK)


def serialize_order(order):
    items = list(order.items.all())
    subtotal = order.total_amount
    delivery_cost = 0

    return {
        "id": str(order.uuid),
        "buyer_id": str(order.buyer.uuid),
        "status": order.status,
        "items": [
            {
                "id": str(item.uuid),
                "sku_id": str(item.sku_id),
                "product_id": str(item.product_id),
                "product_title": item.product_title,
                "sku_name": item.sku_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
            }
            for item in items
        ],
        "subtotal": subtotal,
        "delivery_cost": delivery_cost,
        "total": subtotal + delivery_cost,
        "address": serialize_address(order.address),
        "payment_method": serialize_payment_method(order.payment_method),
        "comment": order.comment or None,
        "cancel_reason": order.cancel_reason or None,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "paid_at": order.paid_at,
        "delivered_at": order.delivered_at,
    }


def serialize_address(address):
    if address is None:
        return None

    return {
        "id": str(address.uuid),
        "country": address.country,
        "region": address.region,
        "city": address.city,
        "street": address.street,
        "building": address.building,
        "apartment": address.apartment,
        "postal_code": address.postal_code,
        "recipient_name": address.recipient_name,
        "recipient_phone": address.recipient_phone,
        "is_default": address.is_default,
        "comment": address.comment,
        "created_at": address.created_at,
    }


def serialize_payment_method(payment_method):
    if payment_method is None:
        return None

    return {
        "id": str(payment_method.uuid),
        "type": payment_method.type,
        "card_last4": payment_method.card_last4,
        "card_brand": payment_method.card_brand,
        "is_default": payment_method.is_default,
        "created_at": payment_method.created_at,
    }


def error_response(code, message, response_status):
    return Response(
        {
            "code": code,
            "message": message,
        },
        status=response_status,
    )
