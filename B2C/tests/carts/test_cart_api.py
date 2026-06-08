import uuid

import pytest
from rest_framework.test import APIClient

from app.buyers.models import Buyer
from app.carts.models import CartItem


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
    product_status="MODERATED",
    product_deleted=False,
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
            "product_status": product_status,
            "product_deleted": product_deleted,
            "image": {"url": "https://cdn.example.test/phone.jpg", "ordering": 0},
        }
    }


@pytest.mark.django_db
def test_add_sku_increments_quantity_if_already_in_cart(api_client, monkeypatch):
    session_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.carts.services.b2b_client.B2BClient.get_skus",
        lambda self, sku_ids: sku_payload(sku_id),
    )

    first_response = api_client.post(
        "/api/v1/cart/items",
        {"sku_id": str(sku_id), "quantity": 1},
        format="json",
        HTTP_X_SESSION_ID=str(session_id),
    )
    second_response = api_client.post(
        "/api/v1/cart/items",
        {"sku_id": str(sku_id), "quantity": 2},
        format="json",
        HTTP_X_SESSION_ID=str(session_id),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.data["items"][0]["quantity"] == 3
    assert CartItem.objects.get(session_id=session_id, sku_id=sku_id).quantity == 3


@pytest.mark.django_db
def test_get_cart_enriched_with_b2b_data(api_client, monkeypatch):
    session_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    product_id = uuid.uuid4()
    CartItem.objects.create(session_id=session_id, sku_id=sku_id, quantity=2)
    monkeypatch.setattr(
        "app.carts.services.b2b_client.B2BClient.get_skus",
        lambda self, sku_ids: sku_payload(
            sku_id,
            product_id=product_id,
            price=1000,
            discount=100,
            available_quantity=7,
        ),
    )

    response = api_client.get("/api/v1/cart", HTTP_X_SESSION_ID=str(session_id))

    assert response.status_code == 200
    assert response.data["items"][0]["product_id"] == str(product_id)
    assert response.data["items"][0]["name"] == "Phone Black"
    assert response.data["items"][0]["unit_price"] == 900
    assert response.data["items"][0]["line_total"] == 1800
    assert response.data["subtotal"] == 1800
    assert response.data["summary"]["checkout_ready"] is True


@pytest.mark.django_db
def test_unavailable_sku_shown_with_reason(api_client, monkeypatch):
    session_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    CartItem.objects.create(session_id=session_id, sku_id=sku_id, quantity=2)
    monkeypatch.setattr(
        "app.carts.services.b2b_client.B2BClient.get_skus",
        lambda self, sku_ids: sku_payload(sku_id, available_quantity=0),
    )

    response = api_client.get("/api/v1/cart", HTTP_X_SESSION_ID=str(session_id))

    assert response.status_code == 200
    assert response.data["items"][0]["is_available"] is False
    assert response.data["items"][0]["unavailable_reason"] == "OUT_OF_STOCK"
    assert response.data["items"][0]["line_total"] == 0
    assert response.data["subtotal"] == 0
    assert response.data["summary"]["checkout_ready"] is False


@pytest.mark.django_db
def test_guest_cart_merged_on_login(api_client, buyer):
    session_id = uuid.uuid4()
    conflicting_sku_id = uuid.uuid4()
    guest_only_sku_id = uuid.uuid4()
    CartItem.objects.create(
        session_id=session_id,
        sku_id=conflicting_sku_id,
        quantity=5,
    )
    CartItem.objects.create(
        session_id=session_id,
        sku_id=guest_only_sku_id,
        quantity=1,
    )
    CartItem.objects.create(user=buyer, sku_id=conflicting_sku_id, quantity=2)

    response = api_client.post(
        "/api/v1/auth/login",
        {"email": buyer.email, "password": "strong-password"},
        format="json",
        HTTP_X_SESSION_ID=str(session_id),
    )

    assert response.status_code == 200
    assert response.data["token_type"] == "Bearer"
    assert CartItem.objects.filter(session_id=session_id).count() == 0
    assert CartItem.objects.get(user=buyer, sku_id=conflicting_sku_id).quantity == 5
    assert CartItem.objects.get(user=buyer, sku_id=guest_only_sku_id).quantity == 1
