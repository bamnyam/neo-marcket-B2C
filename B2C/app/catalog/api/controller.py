from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.catalog.services import (
    ALLOWED_SORTS,
    B2BCatalogClient,
    B2BUnavailableError,
    B2BUpstreamError,
)


INVALID_SORT_MESSAGE = (
    "Invalid sort parameter. Allowed: "
    "rating, popularity, price_asc, price_desc, date_desc, discount_desc"
)

PRODUCT_CARD_FIELDS = (
    "id",
    "slug",
    "title",
    "description",
    "images",
    "status",
    "characteristics",
)

SKU_CARD_FIELDS = (
    "id",
    "name",
    "price",
    "quantity",
    "characteristics",
    "images",
)


class CatalogProxyMixin:
    service_class = B2BCatalogClient

    def _proxy_response(self, method_name, *args):
        try:
            payload = getattr(self.service_class(), method_name)(*args)
        except B2BUnavailableError:
            return Response(
                {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Catalog temporarily unavailable",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except B2BUpstreamError as exc:
            return Response(exc.payload, status=exc.status_code)

        return Response(payload, status=status.HTTP_200_OK)

    def _invalid_request(self, message):
        return Response(
            {
                "code": "INVALID_REQUEST",
                "message": message,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class ProductsController(CatalogProxyMixin, APIView):
    def get(self, request):
        sort = request.query_params.get("sort", "rating")

        if sort not in ALLOWED_SORTS:
            return self._invalid_request(INVALID_SORT_MESSAGE)

        query_params = request.query_params.copy()
        query_params.setdefault("limit", "20")
        query_params.setdefault("offset", "0")
        query_params.setdefault("sort", sort)

        return self._proxy_response("get_products", query_params)


class ProductCardController(CatalogProxyMixin, APIView):
    def get(self, request, product_id):
        try:
            product = self.service_class().get_product(product_id)
        except B2BUnavailableError:
            return Response(
                {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Catalog temporarily unavailable",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except B2BUpstreamError as exc:
            return Response(exc.payload, status=exc.status_code)

        return Response(sanitize_product_card(product), status=status.HTTP_200_OK)


class CategoryFiltersController(CatalogProxyMixin, APIView):
    def get(self, request, category_id):
        return self._proxy_response("get_category_filters", category_id)


class CatalogFacetsController(CatalogProxyMixin, APIView):
    def get(self, request):
        if not request.query_params.get("category_id"):
            return self._invalid_request("category_id is required")

        return self._proxy_response("get_facets", request.query_params)


def sanitize_product_card(product):
    sanitized = {
        field: product.get(field) for field in PRODUCT_CARD_FIELDS if field in product
    }
    if "images" in sanitized:
        sanitized["images"] = [_sanitize_image(image) for image in sanitized["images"]]
    sanitized["skus"] = [_sanitize_sku(sku) for sku in product.get("skus", [])]
    return sanitized


def _sanitize_sku(sku):
    normalized_sku = dict(sku)

    if "quantity" not in normalized_sku:
        normalized_sku["quantity"] = _get_quantity(normalized_sku)

    if "images" in normalized_sku:
        normalized_sku["images"] = [
            _sanitize_image(image) for image in normalized_sku["images"]
        ]
    elif "image" in normalized_sku:
        normalized_sku["images"] = [_sanitize_image(normalized_sku["image"])]

    return {
        field: normalized_sku.get(field)
        for field in SKU_CARD_FIELDS
        if field in normalized_sku
    }


def _get_quantity(sku):
    if "active_quantity" in sku:
        return sku["active_quantity"]

    if "activeQuantity" in sku:
        return sku["activeQuantity"]

    return 0


def _sanitize_image(image):
    if isinstance(image, str):
        return {"url": image, "order": 0}

    normalized_image = dict(image)

    if "order" not in normalized_image and "ordering" in normalized_image:
        normalized_image["order"] = normalized_image["ordering"]

    return {
        "url": normalized_image.get("url"),
        "order": normalized_image.get("order", 0),
    }
