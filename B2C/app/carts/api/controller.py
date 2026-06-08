import uuid

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.carts.api.serializers import (
    CartItemAddSerializer,
    CartItemQuantitySerializer,
)
from app.carts.services import CartIdentity, CartService
from app.carts.services.b2b_client import B2BUnavailableError


class CartController(APIView):
    service_class = CartService

    def get(self, request):
        identity = self._get_identity(request)

        if isinstance(identity, Response):
            return identity

        return self._cart_response(identity)

    def delete(self, request):
        identity = self._get_identity(request)

        if isinstance(identity, Response):
            return identity

        self.service_class().clear(identity)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _cart_response(self, identity, response_status=status.HTTP_200_OK):
        try:
            data = self.service_class().build_cart_response(identity)
        except B2BUnavailableError:
            return self._error(
                "SERVICE_UNAVAILABLE",
                "B2B service is unavailable",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(data, status=response_status)

    def _get_identity(self, request, allow_session_with_user=False):
        invalid_identity = self._reject_client_supplied_identity(request)

        if invalid_identity is not None:
            return invalid_identity

        user = request.user if request.user.is_authenticated else None
        session_id = self._parse_session_id(request)

        if isinstance(session_id, Response):
            return session_id

        if user is not None and not allow_session_with_user:
            return CartIdentity(user=user)

        if user is not None and session_id is not None:
            return CartIdentity(user=user, session_id=session_id)

        if session_id is not None:
            return CartIdentity(session_id=session_id)

        return self._error(
            "MISSING_CART_IDENTITY",
            "Authorization or X-Session-Id is required",
            status.HTTP_400_BAD_REQUEST,
        )

    def _reject_client_supplied_identity(self, request):
        forbidden_fields = {"user_id", "session_id"}

        if forbidden_fields.intersection(request.query_params.keys()):
            return self._error(
                "INVALID_REQUEST",
                "user_id and session_id are not accepted from client input",
                status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(request.data, dict) and forbidden_fields.intersection(
            request.data.keys()
        ):
            return self._error(
                "INVALID_REQUEST",
                "user_id and session_id are not accepted from client input",
                status.HTTP_400_BAD_REQUEST,
            )

        return None

    def _parse_session_id(self, request):
        raw_session_id = request.headers.get("X-Session-Id")

        if not raw_session_id:
            return None

        try:
            return uuid.UUID(str(raw_session_id))
        except ValueError:
            return self._error(
                "INVALID_REQUEST",
                "X-Session-Id must be a valid UUID",
                status.HTTP_400_BAD_REQUEST,
            )

    def _error(self, code, message, response_status):
        return Response(
            {
                "code": code,
                "message": message,
            },
            status=response_status,
        )

    def _parse_sku_id(self, sku_id):
        try:
            return uuid.UUID(str(sku_id))
        except ValueError:
            return self._error(
                "INVALID_REQUEST",
                "sku_id must be a valid UUID",
                status.HTTP_400_BAD_REQUEST,
            )

    def _validate_sku_for_quantity(self, sku_id, quantity):
        try:
            sku = self.service_class().b2b_client.get_skus([sku_id]).get(str(sku_id))
        except B2BUnavailableError:
            return self._error(
                "SERVICE_UNAVAILABLE",
                "B2B service is unavailable",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if sku is None:
            return self._error(
                "NOT_FOUND",
                "SKU not found",
                status.HTTP_404_NOT_FOUND,
            )

        reason = self.service_class()._unavailable_reason(sku)

        if reason is not None:
            return self._error(
                reason,
                "SKU is unavailable",
                status.HTTP_409_CONFLICT,
            )

        if sku["available_quantity"] < quantity:
            return self._error(
                "INSUFFICIENT_STOCK",
                "Insufficient SKU stock",
                status.HTTP_409_CONFLICT,
            )

        return None


class CartItemsController(CartController):
    def post(self, request):
        identity = self._get_identity(request)

        if isinstance(identity, Response):
            return identity

        serializer = CartItemAddSerializer(data=request.data)

        if not serializer.is_valid():
            return self._error(
                "INVALID_REQUEST",
                str(serializer.errors),
                status.HTTP_400_BAD_REQUEST,
            )

        sku_id = serializer.validated_data["sku_id"]
        quantity = serializer.validated_data["quantity"]
        validation_response = self._validate_sku_for_quantity(sku_id, quantity)

        if validation_response is not None:
            return validation_response

        _, created = self.service_class().add_item(identity, sku_id, quantity)

        return self._cart_response(
            identity,
            status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CartItemController(CartController):
    def patch(self, request, sku_id):
        identity = self._get_identity(request)

        if isinstance(identity, Response):
            return identity

        parsed_sku_id = self._parse_sku_id(sku_id)

        if isinstance(parsed_sku_id, Response):
            return parsed_sku_id

        serializer = CartItemQuantitySerializer(data=request.data)

        if not serializer.is_valid():
            return self._error(
                "INVALID_QUANTITY",
                "Quantity must be at least 1",
                status.HTTP_400_BAD_REQUEST,
            )

        quantity = serializer.validated_data["quantity"]
        validation_response = self._validate_sku_for_quantity(parsed_sku_id, quantity)

        if validation_response is not None:
            return validation_response

        item = self.service_class().update_item(identity, parsed_sku_id, quantity)

        if item is None:
            return self._error(
                "NOT_FOUND",
                "Cart item not found",
                status.HTTP_404_NOT_FOUND,
            )

        return self._cart_response(identity)

    def delete(self, request, sku_id):
        identity = self._get_identity(request)

        if isinstance(identity, Response):
            return identity

        parsed_sku_id = self._parse_sku_id(sku_id)

        if isinstance(parsed_sku_id, Response):
            return parsed_sku_id

        self.service_class().delete_item(identity, parsed_sku_id)
        return self._cart_response(identity)


class CartMergeController(CartController):
    def post(self, request):
        identity = self._get_identity(request, allow_session_with_user=True)

        if isinstance(identity, Response):
            return identity

        if identity.user is None:
            return self._error(
                "UNAUTHORIZED",
                "Authorization is required",
                status.HTTP_401_UNAUTHORIZED,
            )

        if identity.session_id is None:
            return self._error(
                "INVALID_REQUEST",
                "X-Session-Id is required",
                status.HTTP_400_BAD_REQUEST,
            )

        self.service_class().merge_guest_cart(identity.user, identity.session_id)

        return self._cart_response(CartIdentity(user=identity.user))


class CartValidateController(CartController):
    def post(self, request):
        identity = self._get_identity(request)

        if isinstance(identity, Response):
            return identity

        cart_response = self._cart_response(identity)

        if cart_response.status_code != status.HTTP_200_OK:
            return cart_response

        issues = []

        for item in cart_response.data["items"]:
            if not item["is_available"]:
                issues.append(
                    {
                        "sku_id": item["sku_id"],
                        "type": item["unavailable_reason"],
                        "message": item["unavailable_message"],
                    }
                )
                continue

            if item["available_quantity"] < item["quantity"]:
                issues.append(
                    {
                        "sku_id": item["sku_id"],
                        "type": "QUANTITY_REDUCED",
                        "message": "Requested quantity exceeds available stock",
                        "old_value": item["quantity"],
                        "new_value": item["available_quantity"],
                    }
                )

        return Response(
            {
                "is_valid": not issues,
                "cart": cart_response.data,
                "issues": issues,
            },
            status=status.HTTP_200_OK,
        )
