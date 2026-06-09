
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("app.buyers.api.urls")),
    path("api/v1/", include("app.catalog.api.urls")),
    path("api/v1/", include("app.carts.api.urls")),
    path("api/v1/", include("app.orders.api.urls")),
]
