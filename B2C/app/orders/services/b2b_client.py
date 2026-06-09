import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from app.carts.services.b2b_client import normalize_skus


class B2BUnavailableError(Exception):
    pass


class ReserveFailedError(Exception):
    def __init__(self, failed_items):
        self.failed_items = failed_items
        super().__init__("Reserve failed")


class B2BOrdersClient:
    timeout = 5

    def get_skus(self, sku_ids):
        if not sku_ids:
            return {}

        query = urllib.parse.urlencode(
            {"sku_ids": ",".join(str(sku_id) for sku_id in sku_ids)}
        )
        payload = self._request_json("GET", f"/api/v1/products?{query}")
        return normalize_skus(payload)

    def reserve(self, idempotency_key, items):
        payload = self._request_json(
            "POST",
            "/api/v1/reserve",
            {
                "idempotency_key": str(idempotency_key),
                "items": [
                    {
                        "sku_id": str(item["sku_id"]),
                        "quantity": item["quantity"],
                    }
                    for item in items
                ],
            },
        )

        if payload.get("reserved") is False:
            raise ReserveFailedError(payload.get("failed_items", []))

        return payload

    def _request_json(self, method, path, body=None):
        url = f"{settings.B2B_URL.rstrip('/')}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Service-Key": settings.B2C_TO_B2B_KEY,
            },
            method=method,
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            payload = _decode_json(exc.read())

            if exc.code == 409:
                raise ReserveFailedError(payload.get("failed_items", [])) from exc

            raise B2BUnavailableError("B2B service is unavailable") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise B2BUnavailableError("B2B service is unavailable") from exc


def _decode_json(raw):
    try:
        return json.loads(raw.decode())
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
