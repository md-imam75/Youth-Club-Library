"""orders/urls.py"""

from django.urls import path
from . import views

urlpatterns = [
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:book_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:book_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:book_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.cart_checkout_view, name='cart_checkout'),
    path('borrow/<int:book_id>/', views.borrow_book_view, name='borrow_book'),
    path('borrow/success/<int:order_id>/', views.borrow_success_view, name='borrow_success'),
    path('checkout/<int:book_id>/<str:order_type>/', views.checkout_view, name='checkout'),
    path('success/<int:order_id>/', views.order_success_view, name='order_success'),
    path('invoice/<int:pk>/', views.order_download_invoice, name='order_download_invoice'),
]
