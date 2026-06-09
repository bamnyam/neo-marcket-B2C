import json
import urllib.parse
import urllib.request

from django.conf import settings


class B2BUnavailableError(Exception):
    pass


class B2BClient:
    timeout = 5

    def get_skus(self, sku_ids):
        if not sku_ids:
            return {}

        query = urllib.parse.urlencode(
            {"sku_ids": ",".join(str(sku_id) for sku_id in sku_ids)}
        )
        url = f"{settings.B2B_URL.rstrip('/')}/api/v1/products?{query}"
        request = urllib.request.Request(
            url,
            headers={"X-Service-Key": settings.B2C_TO_B2B_KEY},
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
        except OSError as exc:
            raise B2BUnavailableError("B2B service is unavailable") from exc

        return normalize_skus(payload)


def normalize_skus(payload):
    products = payload if isinstance(payload, list) else payload.get("items", [])
    result = {}

    for product in products:
        for sku in product.get("skus", []):
            sku_id = sku.get("id") or sku.get("uuid") or sku.get("sku_id")

            if not sku_id:
                continue

            result[str(sku_id)] = {
                "sku_id": str(sku_id),
                "product_id": str(
                    sku.get("product_id")
                    or product.get("id")
                    or product.get("uuid")
                    or ""
                ),
                "product_title": product.get("title") or product.get("name") or "",
                "sku_name": sku.get("name") or "",
                "sku_code": sku.get("sku_code") or sku.get("article") or "",
                "price": int(sku.get("price") or 0),
                "discount": int(sku.get("discount") or 0),
                "available_quantity": _quantity(sku),
                "product_status": product.get("status") or "MODERATED",
                "product_deleted": bool(product.get("deleted", False)),
                "image": _first_image(sku) or _first_image(product),
            }

    return result


def _quantity(sku):
    for field in ("available_quantity", "active_quantity", "activeQuantity"):
        if sku.get(field) is not None:
            return int(sku[field])

    return 0


def _first_image(source):
    image = source.get("image")

    if isinstance(image, dict):
        return image

    if isinstance(image, str):
        return {"url": image}

    images = source.get("images") or []

    if not images:
        return None

    if isinstance(images[0], str):
        return {"url": images[0]}

    return images[0]
