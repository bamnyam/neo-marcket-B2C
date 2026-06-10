from django.urls import path

from app.catalog.api.controller import (
    CatalogFacetsController,
    CategoryFiltersController,
    ProductCardController,
    ProductsController,
)

urlpatterns = [
    path("products/<str:product_id>", ProductCardController.as_view(), name="product-card"),
    path("catalog/products", ProductsController.as_view(), name="catalog-products"),
    path(
        "categories/<str:category_id>/filters",
        CategoryFiltersController.as_view(),
        name="category-filters",
    ),
    path("catalog/facets", CatalogFacetsController.as_view(), name="catalog-facets"),
]
