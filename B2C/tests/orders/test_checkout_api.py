import uuid

import pytest
from rest_framework.test import APIClient

from app.buyers.models import Buyer
from app.carts.services.b2b_client import normalize_skus
from app.orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.orders.services.b2b_client import B2BUnavailableError, ReserveFailedError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def buyer():
    return Buyer.objects.create_user(
        email=f"{uuid.uuid4()}@example.com",
        password="strong-password",
        first_name="Buyer",
    )


def sku_payload(
    sku_id,
    product_id=None,
    price=1000,
    discount=0,
    available_quantity=10,
):
    return {
        str(sku_id): {
            "sku_id": str(sku_id),
            "product_id": str(product_id or uuid.uuid4()),
            "product_title": "Phone",
            "sku_name": "Black",
            "sku_code": "SKU-1",
            "price": price,
            "discount": discount,
            "available_quantity": available_quantity,
            "product_status": "MODERATED",
            "product_deleted": False,
            "image": {"url": "https://cdn.example.test/phone.jpg", "ordering": 0},
        }
    }


@pytest.mark.django_db
def test_checkout_creates_paid_order_with_fixed_prices(api_client, buyer, monkeypatch):
    sku_id = uuid.uuid4()
    product_id = uuid.uuid4()
    idempotency_key = uuid.uuid4()
    reserves = []

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        lambda self, sku_ids: sku_payload(
            sku_id,
            product_id=product_id,
            price=1500,
            discount=200,
        ),
    )
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.reserve",
        lambda self, idem_key, items: reserves.append((idem_key, items))
        or {"reserved": True},
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "idempotency_key": str(idempotency_key),
            "items": [{"sku_id": str(sku_id), "quantity": 2}],
            "delivery_address": "г. Екатеринбург, ул. Мира 19",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == OrderStatus.PAID
    assert response.data["total_amount"] == 2600
    assert response.data["items"][0]["unit_price"] == 1300
    assert response.data["items"][0]["line_total"] == 2600
    assert reserves[0][0] == idempotency_key

    order = Order.objects.get(idempotency_key=idempotency_key)
    item = OrderItem.objects.get(order=order)
    assert order.status == OrderStatus.PAID
    assert order.paid_at is not None
    assert order.total_amount == 2600
    assert item.product_id == product_id
    assert item.unit_price == 1300
    assert item.line_total == 2600
    assert list(
        OrderStatusHistory.objects.filter(order=order).order_by("id").values_list(
            "status_from",
            "status_to",
        )
    ) == [
        (None, OrderStatus.CREATED),
        (OrderStatus.CREATED, OrderStatus.PAID),
    ]


@pytest.mark.django_db
def test_partial_reserve_failure_returns_409(api_client, buyer, monkeypatch):
    ok_sku_id = uuid.uuid4()
    failed_sku_id = uuid.uuid4()
    failed_items = [
        {
            "sku_id": str(failed_sku_id),
            "requested": 2,
            "available": 0,
            "reason": "INSUFFICIENT_STOCK",
        }
    ]

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        lambda self, sku_ids: {
            **sku_payload(ok_sku_id),
            **sku_payload(failed_sku_id, available_quantity=3),
        },
    )

    def reserve_failed(self, idempotency_key, items):
        raise ReserveFailedError(failed_items)

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.reserve",
        reserve_failed,
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "idempotency_key": str(uuid.uuid4()),
            "items": [
                {"sku_id": str(ok_sku_id), "quantity": 1},
                {"sku_id": str(failed_sku_id), "quantity": 2},
            ],
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["code"] == "RESERVE_FAILED"
    assert response.data["failed_items"] == failed_items
    assert Order.objects.count() == 0
    assert OrderItem.objects.count() == 0


@pytest.mark.django_db
def test_idempotency_returns_existing_order(api_client, buyer, monkeypatch):
    sku_id = uuid.uuid4()
    idempotency_key = uuid.uuid4()
    reserve_calls = []

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        lambda self, sku_ids: sku_payload(sku_id, price=1000),
    )
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.reserve",
        lambda self, idem_key, items: reserve_calls.append(items)
        or {"reserved": True},
    )
    api_client.force_authenticate(user=buyer)
    payload = {
        "idempotency_key": str(idempotency_key),
        "items": [{"sku_id": str(sku_id), "quantity": 1}],
    }

    first_response = api_client.post("/api/v1/orders", payload, format="json")
    second_response = api_client.post("/api/v1/orders", payload, format="json")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.data["id"] == first_response.data["id"]
    assert Order.objects.count() == 1
    assert OrderItem.objects.count() == 1
    assert len(reserve_calls) == 1


@pytest.mark.django_db
def test_b2b_unavailable_returns_503(api_client, buyer, monkeypatch):
    def b2b_unavailable(self, sku_ids):
        raise B2BUnavailableError("B2B service is unavailable")

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        b2b_unavailable,
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "idempotency_key": str(uuid.uuid4()),
            "items": [{"sku_id": str(uuid.uuid4()), "quantity": 1}],
        },
        format="json",
    )

    assert response.status_code == 503
    assert response.data["code"] == "B2B_UNAVAILABLE"
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_rejects_cart_id(api_client, buyer):
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "idempotency_key": str(uuid.uuid4()),
            "cart_id": str(uuid.uuid4()),
            "items": [{"sku_id": str(uuid.uuid4()), "quantity": 1}],
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_REQUEST"
    assert Order.objects.count() == 0


def test_b2b_product_contract_active_quantity_is_supported():
    sku_id = uuid.uuid4()

    sku_map = normalize_skus(
        [
            {
                "id": str(uuid.uuid4()),
                "title": "Phone",
                "status": "MODERATED",
                "skus": [
                    {
                        "id": str(sku_id),
                        "name": "Black",
                        "price": 1000,
                        "activeQuantity": 7,
                    }
                ],
            }
        ]
    )

    assert sku_map[str(sku_id)]["available_quantity"] == 7
