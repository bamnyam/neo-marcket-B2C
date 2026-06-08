from django.urls import path

from app.carts.api.controller import (
    CartController,
    CartItemController,
    CartItemsController,
    CartMergeController,
    CartValidateController,
)

urlpatterns = [
    path("cart", CartController.as_view(), name="cart"),
    path("cart/items", CartItemsController.as_view(), name="cart-items"),
    path("cart/items/<str:sku_id>", CartItemController.as_view(), name="cart-item"),
    path("cart/validate", CartValidateController.as_view(), name="cart-validate"),
    path("cart/merge", CartMergeController.as_view(), name="cart-merge"),
]
