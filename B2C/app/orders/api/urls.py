from django.urls import path

from app.orders.api.controller import OrdersController

urlpatterns = [
    path("orders", OrdersController.as_view(), name="orders"),
]
