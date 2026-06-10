from django.urls import path

from app.orders.api.controller import OrderCancelController, OrdersController

urlpatterns = [
    path("orders", OrdersController.as_view(), name="orders"),
    path(
        "orders/<uuid:order_id>/cancel",
        OrderCancelController.as_view(),
        name="order-cancel",
    ),
]
