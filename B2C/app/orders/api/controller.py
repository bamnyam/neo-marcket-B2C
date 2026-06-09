from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.orders.api.serializers import CheckoutSerializer
from app.orders.services import B2BUnavailableError, CheckoutService, ReserveFailedError


class OrdersController(APIView):
    permission_classes = [IsAuthenticated]
    service_class = CheckoutService

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)

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
                idempotency_key=serializer.validated_data["idempotency_key"],
                items=serializer.validated_data["items"],
                delivery_address=serializer.validated_data.get("delivery_address"),
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
        items = list(order.items.all())

        return {
            "id": str(order.uuid),
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
            "total_amount": order.total_amount,
            "delivery_address": order.delivery_address,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    def _error(self, code, message, response_status):
        return Response(
            {
                "code": code,
                "message": message,
            },
            status=response_status,
        )

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
