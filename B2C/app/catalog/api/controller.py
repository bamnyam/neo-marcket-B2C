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
    "Invalid sort parameter. Allowed: price_asc, price_desc, popularity, new"
)

PRODUCT_CARD_FIELDS = (
    "id",
    "slug",
    "name",
    "description",
    "images",
    "status",
    "characteristics",
    "min_price",
    "has_stock",
)

SKU_CARD_FIELDS = (
    "id",
    "name",
    "price",
    "available_quantity",
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
        sort = request.query_params.get("sort", "popularity")

        if sort not in ALLOWED_SORTS:
            return self._invalid_request(INVALID_SORT_MESSAGE)

        query_params = request.query_params.copy()
        query_params.setdefault("limit", "20")
        query_params.setdefault("offset", "0")
        query_params.setdefault("sort", sort)

        try:
            payload = self.service_class().get_products(query_params)
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

        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            payload = {
                **payload,
                "items": [_sanitize_product_summary(item) for item in payload["items"]],
            }

        return Response(payload, status=status.HTTP_200_OK)


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
    normalized_product = dict(product)
    normalized_product["name"] = product.get("name") or product.get("title")

    skus = [_sanitize_sku(sku) for sku in product.get("skus", [])]
    normalized_product["min_price"] = _get_min_price(skus)
    normalized_product["has_stock"] = any(
        sku.get("available_quantity", 0) > 0 for sku in skus
    )

    sanitized = {
        field: normalized_product.get(field)
        for field in PRODUCT_CARD_FIELDS
        if field in normalized_product
    }
    if "images" in sanitized:
        sanitized["images"] = [_sanitize_image(image) for image in sanitized["images"]]
    sanitized["skus"] = skus
    return sanitized


def _sanitize_product_summary(product):
    normalized_product = dict(product)
    normalized_product["name"] = product.get("name") or product.get("title")

    if "min_price" not in normalized_product:
        normalized_product["min_price"] = _get_summary_min_price(normalized_product)

    if "has_stock" not in normalized_product:
        normalized_product["has_stock"] = _get_summary_has_stock(normalized_product)

    normalized_product.pop("title", None)
    normalized_product.pop("price", None)
    normalized_product.pop("in_stock", None)
    return normalized_product


def _sanitize_sku(sku):
    normalized_sku = dict(sku)

    if "available_quantity" not in normalized_sku:
        normalized_sku["available_quantity"] = _get_quantity(normalized_sku)

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
    if "available_quantity" in sku:
        return sku["available_quantity"]

    if "active_quantity" in sku:
        return sku["active_quantity"]

    if "activeQuantity" in sku:
        return sku["activeQuantity"]

    if "quantity" in sku:
        return sku["quantity"]

    return 0


def _get_min_price(skus):
    prices = [sku["price"] for sku in skus if sku.get("price") is not None]
    if not prices:
        return None

    return min(prices)


def _get_summary_min_price(product):
    if product.get("price") is not None:
        return product["price"]

    return _get_min_price([_sanitize_sku(sku) for sku in product.get("skus", [])])


def _get_summary_has_stock(product):
    if product.get("in_stock") is not None:
        return product["in_stock"]

    skus = [_sanitize_sku(sku) for sku in product.get("skus", [])]
    if skus:
        return any(sku.get("available_quantity", 0) > 0 for sku in skus)

    return False


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
