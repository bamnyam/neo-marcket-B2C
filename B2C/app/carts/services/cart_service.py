from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from app.carts.models import CartItem
from app.carts.services.b2b_client import B2BClient, B2BUnavailableError


@dataclass(frozen=True)
class CartIdentity:
    user: object | None = None
    session_id: UUID | None = None

    @property
    def filter_kwargs(self):
        if self.user is not None:
            return {"user": self.user}

        return {"session_id": self.session_id}

    @property
    def create_kwargs(self):
        return self.filter_kwargs

    @property
    def response_id(self):
        if self.user is not None:
            return str(self.user.uuid)

        return str(self.session_id)


class CartService:
    unavailable_messages = {
        "OUT_OF_STOCK": "Нет в наличии",
        "PRODUCT_BLOCKED": "Товар недоступен",
        "PRODUCT_DELETED": "Товар удален",
        "PRODUCT_DELISTED": "Товар удален",
        "ON_MODERATION": "Товар временно недоступен",
    }

    def __init__(self, b2b_client=None):
        self.b2b_client = b2b_client or B2BClient()

    @transaction.atomic
    def add_item(self, identity, sku_id, quantity):
        item, created = CartItem.objects.select_for_update().get_or_create(
            **identity.filter_kwargs,
            sku_id=sku_id,
            defaults={
                "quantity": quantity,
                **identity.create_kwargs,
            },
        )

        if not created:
            item.quantity += quantity
            item.save(update_fields=["quantity", "updated_at"])

        return item, created

    @transaction.atomic
    def update_item(self, identity, sku_id, quantity):
        item = self._items(identity).select_for_update().filter(sku_id=sku_id).first()

        if item is None:
            return None

        item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])
        return item

    @transaction.atomic
    def delete_item(self, identity, sku_id):
        item = self._items(identity).select_for_update().filter(sku_id=sku_id).first()

        if item is None:
            return False

        item.delete()
        return True

    def clear(self, identity):
        self._items(identity).delete()

    @transaction.atomic
    def merge_guest_cart(self, user, session_id):
        guest_items = list(
            CartItem.objects.select_for_update().filter(session_id=session_id)
        )

        for guest_item in guest_items:
            auth_item = (
                CartItem.objects.select_for_update()
                .filter(user=user, sku_id=guest_item.sku_id)
                .first()
            )

            if auth_item is None:
                guest_item.user = user
                guest_item.session_id = None
                guest_item.save(update_fields=["user", "session_id", "updated_at"])
                continue

            auth_item.quantity = max(auth_item.quantity, guest_item.quantity)
            auth_item.save(update_fields=["quantity", "updated_at"])
            guest_item.delete()

        CartItem.objects.filter(session_id=session_id).delete()

    def build_cart_response(self, identity):
        items = list(self._items(identity).order_by("created_at"))
        sku_map = self._get_sku_map(items)
        response_items = [self._build_item(item, sku_map.get(str(item.sku_id))) for item in items]
        subtotal = sum(item["line_total"] for item in response_items)
        unavailable_count = sum(1 for item in response_items if not item["is_available"])
        is_valid = unavailable_count == 0 and all(
            item["available_quantity"] >= item["quantity"] for item in response_items
        )

        return {
            "id": identity.response_id,
            "items": response_items,
            "items_count": sum(item.quantity for item in items),
            "subtotal": subtotal,
            "is_valid": is_valid,
            "updated_at": max((item.updated_at for item in items), default=None),
            "summary": {
                "total_amount": subtotal,
                "total_items": sum(item.quantity for item in items),
                "unavailable_count": unavailable_count,
                "checkout_ready": is_valid and bool(items),
            },
            "checkout_payload": {
                "items": [
                    {
                        "sku_id": item["sku_id"],
                        "quantity": item["quantity"],
                    }
                    for item in response_items
                    if item["is_available"]
                    and item["available_quantity"] >= item["quantity"]
                ]
            },
        }

    def _items(self, identity):
        return CartItem.objects.filter(**identity.filter_kwargs)

    def _get_sku_map(self, items):
        try:
            return self.b2b_client.get_skus([item.sku_id for item in items])
        except B2BUnavailableError:
            raise

    def _build_item(self, item, sku):
        if sku is None:
            return self._unavailable_item(item, "PRODUCT_DELETED")

        unavailable_reason = self._unavailable_reason(sku)
        unit_price = max(sku["price"] - sku["discount"], 0)
        is_available = unavailable_reason is None

        return {
            "id": str(item.uuid),
            "sku_id": str(item.sku_id),
            "product_id": sku["product_id"],
            "name": self._item_name(sku),
            "sku_code": sku["sku_code"],
            "quantity": item.quantity,
            "unit_price": unit_price,
            "unit_price_at_add": item.unit_price_at_add,
            "line_total": unit_price * item.quantity if is_available else 0,
            "available_quantity": sku["available_quantity"],
            "is_available": is_available,
            "available": is_available,
            "unavailable_reason": unavailable_reason,
            "unavailable_message": self.unavailable_messages.get(unavailable_reason, ""),
            "image": sku["image"],
        }

    def _unavailable_item(self, item, reason):
        return {
            "id": str(item.uuid),
            "sku_id": str(item.sku_id),
            "product_id": None,
            "name": "",
            "sku_code": "",
            "quantity": item.quantity,
            "unit_price": 0,
            "unit_price_at_add": item.unit_price_at_add,
            "line_total": 0,
            "available_quantity": 0,
            "is_available": False,
            "available": False,
            "unavailable_reason": reason,
            "unavailable_message": self.unavailable_messages[reason],
            "image": None,
        }

    def _unavailable_reason(self, sku):
        if sku["product_deleted"]:
            return "PRODUCT_DELETED"

        if sku["product_status"] in {"BLOCKED", "HARD_BLOCKED"}:
            return "PRODUCT_BLOCKED"

        if sku["product_status"] == "ON_MODERATION":
            return "ON_MODERATION"

        if sku["available_quantity"] <= 0:
            return "OUT_OF_STOCK"

        return None

    def _item_name(self, sku):
        if sku["sku_name"]:
            return f"{sku['product_title']} {sku['sku_name']}".strip()

        return sku["product_title"]
