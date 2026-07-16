"""panel/urls.py — Custom admin panel URL patterns."""

from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('',                        views.admin_dashboard,        name='admin_dashboard'),
    # Membership requests
    path('memberships/',            views.admin_memberships,       name='admin_memberships'),
    path('memberships/<int:pk>/action/', views.admin_membership_action, name='admin_membership_action'),
    # Orders
    path('orders/',                 views.admin_orders,            name='admin_orders'),
    path('orders/<int:pk>/action/', views.admin_order_action,      name='admin_order_action'),
    path('orders/<int:pk>/approve-borrow/', views.admin_approve_borrow, name='admin_approve_borrow'),
    # Users
    path('users/',                  views.admin_users,             name='admin_users'),
    path('users/<int:pk>/',         views.admin_user_detail,       name='admin_user_detail'),
    path('create-ajax/',            views.admin_create_ajax,       name='admin_create_ajax'),
    # Books CRUD
    path('books/',                  views.admin_books,             name='admin_books'),
    path('books/add/',              views.admin_book_add,          name='admin_book_add'),
    path('books/<int:pk>/edit/',    views.admin_book_edit,         name='admin_book_edit'),
    path('books/<int:pk>/delete/',  views.admin_book_delete,       name='admin_book_delete'),
    # Plans CRUD
    path('plans/',                  views.admin_plans,             name='admin_plans'),
    path('plans/add/',              views.admin_plan_add,          name='admin_plan_add'),
    path('plans/<int:pk>/edit/',    views.admin_plan_edit,         name='admin_plan_edit'),
    path('plans/<int:pk>/delete/',  views.admin_plan_delete,       name='admin_plan_delete'),

    # Authors CRUD
    path('authors/',                views.admin_authors,           name='admin_authors'),
    path('authors/add/',            views.admin_author_add,        name='admin_author_add'),
    path('authors/<int:pk>/edit/',   views.admin_author_edit,       name='admin_author_edit'),
    path('authors/<int:pk>/delete/', views.admin_author_delete,     name='admin_author_delete'),

    # Publications CRUD
    path('publications/',                views.admin_publications,           name='admin_publications'),
    path('publications/add/',            views.admin_publication_add,        name='admin_publication_add'),
    path('publications/<int:pk>/edit/',   views.admin_publication_edit,       name='admin_publication_edit'),
    path('publications/<int:pk>/delete/', views.admin_publication_delete,     name='admin_publication_delete'),

    # Categories CRUD
    path('categories/',                views.admin_categories,           name='admin_categories'),
    path('categories/add/',            views.admin_category_add,        name='admin_category_add'),
    path('categories/<int:pk>/edit/',   views.admin_category_edit,       name='admin_category_edit'),
    path('categories/<int:pk>/delete/', views.admin_category_delete,     name='admin_category_delete'),

    # Social Media Links CRUD
    path('social-links/',                views.admin_social_links,           name='admin_social_links'),
    path('social-links/add/',            views.admin_social_link_add,        name='admin_social_link_add'),
    path('social-links/<int:pk>/edit/',   views.admin_social_link_edit,       name='admin_social_link_edit'),
    path('social-links/<int:pk>/delete/', views.admin_social_link_delete,     name='admin_social_link_delete'),

    # Offline Billing System
    path('billing/',                     views.admin_bill_list,              name='admin_bill_list'),
    path('billing/make/',                views.admin_make_bill,              name='admin_make_bill'),
    path('billing/<int:pk>/pdf/',        views.admin_bill_download_pdf,      name='admin_bill_download_pdf'),
    path('billing/search-books/',        views.admin_book_search_ajax,       name='admin_book_search_ajax'),

    # Book Requests Management
    path('requests/',                    views.admin_book_requests,          name='admin_book_requests'),
    path('requests/<int:pk>/action/',    views.admin_book_request_action,    name='admin_book_request_action'),
    path('requests/<int:pk>/delete/',    views.admin_book_request_delete,    name='admin_book_request_delete'),

    # Reports
    path('reports/sales/',               views.admin_sales_report,           name='admin_sales_report'),
    path('reports/sales/pdf/',           views.admin_sales_report_pdf,       name='admin_sales_report_pdf'),

    # Testimonials CRUD
    path('testimonials/',                views.admin_testimonials,           name='admin_testimonials'),
    path('testimonials/add/',            views.admin_testimonial_add,        name='admin_testimonial_add'),
    path('testimonials/<int:pk>/edit/',   views.admin_testimonial_edit,       name='admin_testimonial_edit'),
    path('testimonials/<int:pk>/delete/', views.admin_testimonial_delete,     name='admin_testimonial_delete'),

    # Delivery Options CRUD
    path('delivery-options/',                views.admin_delivery_options,           name='admin_delivery_options'),
    path('delivery-options/add/',            views.admin_delivery_option_add,        name='admin_delivery_option_add'),
    path('delivery-options/<int:pk>/edit/',   views.admin_delivery_option_edit,       name='admin_delivery_option_edit'),
    path('delivery-options/<int:pk>/delete/', views.admin_delivery_option_delete,     name='admin_delivery_option_delete'),
]
