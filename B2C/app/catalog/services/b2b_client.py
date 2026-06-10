import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


ALLOWED_SORTS = (
    "price_asc",
    "price_desc",
    "popularity",
    "new",
)


class B2BUnavailableError(Exception):
    pass


class B2BUpstreamError(Exception):
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {
            "code": "UPSTREAM_ERROR",
            "message": "B2B service returned an error",
        }
        super().__init__(self.payload.get("message", "B2B service returned an error"))


class B2BCatalogClient:
    timeout = 5

    def get_products(self, query_params):
        return self._get("/api/v1/products", query_params)

    def get_product(self, product_id):
        return self._get(f"/api/v1/products/{product_id}")

    def get_category_filters(self, category_id):
        return self._get(f"/api/v1/categories/{category_id}/filters")

    def get_facets(self, query_params):
        return self._get("/api/v1/catalog/facets", query_params)

    def _get(self, path, query_params=None):
        query = _encode_query_params(query_params)
        url = f"{settings.B2B_URL.rstrip('/')}{path}"

        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={"X-Service-Key": settings.B2C_TO_B2B_KEY},
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return _decode_json(response.read())
        except urllib.error.HTTPError as exc:
            raise B2BUpstreamError(exc.code, _decode_json(exc.read())) from exc
        except (OSError, TimeoutError) as exc:
            raise B2BUnavailableError("B2B service is unavailable") from exc


def _encode_query_params(query_params):
    if not query_params:
        return ""

    if hasattr(query_params, "lists"):
        pairs = []

        for key, values in query_params.lists():
            for value in values:
                pairs.append((key, value))

        return urllib.parse.urlencode(pairs)

    return urllib.parse.urlencode(query_params, doseq=True)


def _decode_json(raw_body):
    if not raw_body:
        return {}

    try:
        return json.loads(raw_body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "code": "UPSTREAM_ERROR",
            "message": "B2B service returned a non-JSON response",
        }
