"""catalog/urls.py"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('about/', views.about_view, name='about'),
    path('books/', views.books_view, name='books'),
    path('books/<int:pk>/', views.book_detail_view, name='book_detail'),
    path('books/author/<int:pk>/', views.books_by_author_view, name='books_by_author'),
    path('books/publication/<int:pk>/', views.books_by_publication_view, name='books_by_publication'),
    path('books/category/<slug:slug>/', views.books_by_category_view, name='books_by_category'),
    path('authors/', views.authors_view, name='authors'),
    path('publications/', views.publications_view, name='publications'),
    path('categories/', views.categories_view, name='categories'),
    path('request-book/', views.request_book_view, name='request_book'),
    path('waitlist/join/<int:pk>/', views.join_waitlist, name='join_waitlist'),
]
