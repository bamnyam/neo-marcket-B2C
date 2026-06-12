import uuid

import pytest
from rest_framework.test import APIClient

from app.buyers.models import Address, Buyer, PaymentMethod, PaymentMethodType
from app.orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.orders.services.b2b_client import B2BUnavailableError


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


@pytest.fixture
def other_buyer():
    return Buyer.objects.create_user(
        email=f"{uuid.uuid4()}@example.com",
        password="strong-password",
        first_name="Other",
    )


@pytest.fixture
def address(buyer):
    return Address.objects.create(
        buyer=buyer,
        country="Россия",
        region="Свердловская область",
        city="Екатеринбург",
        street="Мира",
        building="19",
        apartment="42",
        postal_code="620000",
        recipient_name="Buyer",
        recipient_phone="+79990000000",
    )


@pytest.fixture
def payment_method(buyer):
    return PaymentMethod.objects.create(
        buyer=buyer,
        type=PaymentMethodType.CARD,
        card_last4="1234",
        card_brand=PaymentMethod.CardBrand.MIR,
    )


def create_order(
    buyer,
    address=None,
    payment_method=None,
    status=OrderStatus.PAID,
):
    order = Order.objects.create(
        buyer=buyer,
        status=status,
        idempotency_key=uuid.uuid4(),
        total_amount=2600,
        address=address,
        payment_method=payment_method,
    )
    OrderItem.objects.create(
        order=order,
        sku_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        name="Phone Black",
        sku_name="Black",
        quantity=2,
        unit_price=1300,
        line_total=2600,
    )

    return order


@pytest.mark.django_db
def test_cancel_paid_order_transitions_to_cancelled(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    order = create_order(buyer, address, payment_method)
    unreserve_calls = []

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.unreserve",
        lambda self, order_id, items: unreserve_calls.append((order_id, items))
        or {"unreserved": True},
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(f"/api/v1/orders/{order.uuid}/cancel")

    assert response.status_code == 200
    assert response.data["id"] == str(order.uuid)
    assert response.data["status"] == OrderStatus.CANCELLED
    assert unreserve_calls == [
        (
            order.uuid,
            [
                {
                    "sku_id": order.items.get().sku_id,
                    "quantity": 2,
                }
            ],
        )
    ]

    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert OrderStatusHistory.objects.filter(
        order=order,
        status_from=OrderStatus.PAID,
        status_to=OrderStatus.CANCELLED,
        reason="cancel_unreserve_success",
    ).exists()


@pytest.mark.django_db
def test_unreserve_failure_transitions_to_cancel_pending(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    order = create_order(buyer, address, payment_method)

    def unreserve_failed(self, order_id, items):
        raise B2BUnavailableError("B2B service is unavailable")

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.unreserve",
        unreserve_failed,
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(f"/api/v1/orders/{order.uuid}/cancel")

    assert response.status_code == 200
    assert response.data["status"] == OrderStatus.CANCEL_PENDING

    order.refresh_from_db()
    assert order.status == OrderStatus.CANCEL_PENDING
    assert OrderStatusHistory.objects.filter(
        order=order,
        status_from=OrderStatus.PAID,
        status_to=OrderStatus.CANCEL_PENDING,
        reason="cancel_unreserve_pending",
    ).exists()


@pytest.mark.django_db
def test_cancel_assembling_order_transitions_to_cancelled(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    order = create_order(
        buyer,
        address,
        payment_method,
        status=OrderStatus.ASSEMBLING,
    )
    unreserve_calls = []
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.unreserve",
        lambda self, order_id, items: unreserve_calls.append((order_id, items))
        or {"unreserved": True},
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(f"/api/v1/orders/{order.uuid}/cancel")

    assert response.status_code == 200
    assert response.data["status"] == OrderStatus.CANCELLED
    assert len(unreserve_calls) == 1

    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert OrderStatusHistory.objects.filter(
        order=order,
        status_from=OrderStatus.ASSEMBLING,
        status_to=OrderStatus.CANCELLED,
        reason="cancel_unreserve_success",
    ).exists()

@pytest.mark.django_db
def test_cancel_delivering_order_transitions_to_cancelled(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    order = create_order(
        buyer,
        address,
        payment_method,
        status=OrderStatus.DELIVERING,
    )
    unreserve_calls = []
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.unreserve",
        lambda self, order_id, items: unreserve_calls.append((order_id, items))
        or {"unreserved": True},
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(f"/api/v1/orders/{order.uuid}/cancel")

    assert response.status_code == 200
    assert response.data["status"] == OrderStatus.CANCELLED
    assert len(unreserve_calls) == 1

    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert OrderStatusHistory.objects.filter(
        order=order,
        status_from=OrderStatus.DELIVERING,
        status_to=OrderStatus.CANCELLED,
        reason="cancel_unreserve_success",
    ).exists()

@pytest.mark.django_db
def test_cancel_delivered_order_returns_409(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    order = create_order(
        buyer,
        address,
        payment_method,
        status=OrderStatus.DELIVERED,
    )
    unreserve_calls = []
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.unreserve",
        lambda self, order_id, items: unreserve_calls.append((order_id, items))
        or {"unreserved": True},
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(f"/api/v1/orders/{order.uuid}/cancel")

    assert response.status_code == 409
    assert response.data["code"] == "CANCEL_NOT_ALLOWED"
    assert response.data["current_status"] == OrderStatus.DELIVERED
    assert unreserve_calls == []

    order.refresh_from_db()
    assert order.status == OrderStatus.DELIVERED

@pytest.mark.django_db
def test_other_user_order_returns_404(
    api_client,
    buyer,
    other_buyer,
    monkeypatch,
):
    order = create_order(other_buyer)
    unreserve_calls = []
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.unreserve",
        lambda self, order_id, items: unreserve_calls.append((order_id, items)),
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(f"/api/v1/orders/{order.uuid}/cancel")

    assert response.status_code == 404
    assert response.data["code"] == "ORDER_NOT_FOUND"
    assert unreserve_calls == []

    order.refresh_from_db()
    assert order.status == OrderStatus.PAID
