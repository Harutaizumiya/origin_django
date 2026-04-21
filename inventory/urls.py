from django.urls import path

from inventory.views import BatchCollectionView, ProductCategoriesView, ProductCollectionView, ProductDetailView

urlpatterns = [
    path("products", ProductCollectionView.as_view(), name="product-collection"),
    path("products/categories", ProductCategoriesView.as_view(), name="product-categories"),
    path("products/<int:product_id>", ProductDetailView.as_view(), name="product-detail"),
    path("batches", BatchCollectionView.as_view(), name="batch-collection"),
]
