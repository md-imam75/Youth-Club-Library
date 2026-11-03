from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Q, Count, Avg
from .models import Author, Publication, Category, Book, BookReview, BookRequest, BookRequestItem, WaitlistEntry, SiteTestimonial
from accounts.models import CustomUser, UserMembership, MembershipPlan
from youth_club_library.throttle import is_throttled


def home_view(request):
    """Home page: hero, carousels, counters, CTA."""
    featured_books = Book.objects.filter(is_featured=True, is_upcoming=False).select_related(
        'author', 'publication', 'category'
    )[:12]
    new_books = Book.objects.filter(is_new=True, is_upcoming=False).select_related(
        'author', 'publication', 'category'
    )[:12]
    upcoming_books = Book.objects.filter(is_upcoming=True).select_related(
        'author', 'publication', 'category'
    )[:12]

    # Cache homepage counters for 60s to avoid 4 COUNT(*) queries on every landing page hit
    stats = cache.get('home_stats_v1')
    if stats is None:
        stats = {
            'total_members': UserMembership.objects.filter(status='Active').count(),
            'total_books': Book.objects.filter(is_upcoming=False).count(),
            'total_authors': Author.objects.count(),
            'total_categories': Category.objects.count(),
        }
        cache.set('home_stats_v1', stats, 60)

    # Active testimonials & membership plans
    testimonials = SiteTestimonial.objects.filter(is_active=True)
    plans = MembershipPlan.objects.filter(is_active=True)

    context = {
        'featured_books': featured_books,
        'new_books': new_books,
        'upcoming_books': upcoming_books,
        'total_members': stats['total_members'],
        'total_books': stats['total_books'],
        'total_authors': stats['total_authors'],
        'total_categories': stats['total_categories'],
        'testimonials': testimonials,
        'plans': plans,
        'page_title': 'Home',
    }
    return render(request, 'home.html', context)


def about_view(request):
    """About Us page: story, vision, 5 pillars, schedule, and live stats."""
    stats = cache.get('home_stats_v1')
    if stats is None:
        stats = {
            'total_members': UserMembership.objects.filter(status='Active').count(),
            'total_books': Book.objects.filter(is_upcoming=False).count(),
            'total_authors': Author.objects.count(),
            'total_categories': Category.objects.count(),
        }
        cache.set('home_stats_v1', stats, 60)

    context = {
        'page_title': 'About Us',
        'total_members': stats['total_members'],
        'total_books': stats['total_books'],
        'total_authors': stats['total_authors'],
        'total_categories': stats['total_categories'],
    }
    return render(request, 'catalog/about.html', context)


def books_view(request):
    """All books grid with search."""
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'newest')

    books = Book.objects.select_related('author', 'publication', 'category').filter(
        is_upcoming=False
    ).annotate(
        _review_count=Count('reviews', distinct=True),
        _avg_rating=Avg('reviews__rating'),
    )

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__name__icontains=query) |
            Q(publication__name__icontains=query) |
            Q(category__name__icontains=query)
        )

    # Price range filtering
    from django.db.models.functions import Coalesce
    from django.db.models import Max
    import math

    # Cache max price across ALL books for 5 minutes (invalidated on Book.save)
    slider_max = cache.get('catalog_slider_max_v1')
    if slider_max is None:
        max_price_val = Book.objects.filter(is_upcoming=False).annotate(
            effective_price=Coalesce('offer_price', 'regular_price')
        ).aggregate(max_p=Max('effective_price'))['max_p'] or 0
        slider_max = int(math.ceil(max_price_val / 100) * 100) if max_price_val else 5000
        cache.set('catalog_slider_max_v1', slider_max, 300)

    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')

    if price_min:
        try:
            books = books.annotate(
                _eff_price_min=Coalesce('offer_price', 'regular_price')
            ).filter(_eff_price_min__gte=int(price_min))
        except (ValueError, TypeError):
            pass

    if price_max:
        try:
            books = books.annotate(
                _eff_price_max=Coalesce('offer_price', 'regular_price')
            ).filter(_eff_price_max__lte=int(price_max))
        except (ValueError, TypeError):
            pass

    # Sorting
    if sort_by == 'featured':
        books = books.order_by('-is_featured', '-created_at')
    elif sort_by == 'best_selling':
        books = books.annotate(sales_count=Count('orders', distinct=True)).order_by('-sales_count', '-created_at')
    elif sort_by == 'alpha_asc':
        books = books.order_by('title')
    elif sort_by == 'alpha_desc':
        books = books.order_by('-title')
    elif sort_by == 'price_asc':
        books = books.annotate(
            current_price=Coalesce('offer_price', 'regular_price')
        ).order_by('current_price')
    elif sort_by == 'price_desc':
        books = books.annotate(
            current_price=Coalesce('offer_price', 'regular_price')
        ).order_by('-current_price')
    elif sort_by == 'date_asc':
        books = books.order_by('created_at')
    elif sort_by == 'relevance':
        if not query:
            books = books.order_by('-created_at')
    else:
        books = books.order_by('-created_at')

    # Pagination (paginator.count computes total_count once instead of running a duplicate COUNT query)
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(books, 36)
    total_count = paginator.count
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'books': page_obj,
        'query': query,
        'sort_by': sort_by,
        'page_title': 'All Books',
        'total_count': total_count,
        'slider_max': slider_max,
        'price_min': price_min,
        'price_max': price_max,
    }
    return render(request, 'catalog/books.html', context)


def book_detail_view(request, pk):
    """Book detail: Buy/Borrow buttons, reviews, and related books."""
    book = get_object_or_404(
        Book.objects.select_related('author', 'publication', 'category').annotate(
            _review_count=Count('reviews', distinct=True),
            _avg_rating=Avg('reviews__rating'),
        ),
        pk=pk
    )
    reviews = list(book.reviews.select_related('user').all())

    # Handle review submission
    user_review = None
    if request.user.is_authenticated:
        for rev in reviews:
            if rev.user_id == request.user.id:
                user_review = rev
                break

        if request.method == 'POST' and 'submit_review' in request.POST:
            if user_review:
                messages.warning(request, 'You have already reviewed this book.')
            else:
                rating = request.POST.get('rating')
                review_text = request.POST.get('review_text', '').strip()[:2000]
                try:
                    rating_int = int(rating)
                except (ValueError, TypeError):
                    rating_int = 0

                if 1 <= rating_int <= 5 and review_text:
                    BookReview.objects.create(
                        user=request.user,
                        book=book,
                        rating=rating_int,
                        review_text=review_text,
                    )
                    messages.success(request, 'Your review has been submitted. Thank you!')
                    return redirect('book_detail', pk=book.pk)
                else:
                    messages.error(request, 'Please provide a valid rating (1–5) and review text.')

    # Related books by Category, Author, and Publication
    related_category_books = Book.objects.filter(
        category=book.category, is_upcoming=False
    ).exclude(pk=book.pk).select_related('author')[:6] if book.category_id else []

    related_author_books = Book.objects.filter(
        author=book.author, is_upcoming=False
    ).exclude(pk=book.pk).select_related('author')[:6] if book.author_id else []

    related_publication_books = Book.objects.filter(
        publication=book.publication, is_upcoming=False
    ).exclude(pk=book.pk).select_related('author')[:6] if book.publication_id else []

    context = {
        'book': book,
        'reviews': reviews,
        'user_review': user_review,
        'related_category_books': related_category_books,
        'related_author_books': related_author_books,
        'related_publication_books': related_publication_books,
        'page_title': book.title,
    }
    return render(request, 'catalog/book_detail.html', context)


def _filter_and_sort_books(books_qs, request):
    """Helper to apply search query, sorting, and pagination to book querysets."""
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'newest')

    books_qs = books_qs.annotate(
        _review_count=Count('reviews', distinct=True),
        _avg_rating=Avg('reviews__rating'),
    )

    if query:
        books_qs = books_qs.filter(
            Q(title__icontains=query) |
            Q(author__name__icontains=query) |
            Q(publication__name__icontains=query) |
            Q(category__name__icontains=query)
        )

    # Sorting
    if sort_by == 'featured':
        books_qs = books_qs.order_by('-is_featured', '-created_at')
    elif sort_by == 'best_selling':
        books_qs = books_qs.annotate(sales_count=Count('orders', distinct=True)).order_by('-sales_count', '-created_at')
    elif sort_by == 'alpha_asc':
        books_qs = books_qs.order_by('title')
    elif sort_by == 'alpha_desc':
        books_qs = books_qs.order_by('-title')
    elif sort_by == 'price_asc':
        from django.db.models.functions import Coalesce
        books_qs = books_qs.annotate(
            current_price=Coalesce('offer_price', 'regular_price')
        ).order_by('current_price')
    elif sort_by == 'price_desc':
        from django.db.models.functions import Coalesce
        books_qs = books_qs.annotate(
            current_price=Coalesce('offer_price', 'regular_price')
        ).order_by('-current_price')
    elif sort_by == 'date_asc':
        books_qs = books_qs.order_by('created_at')
    else:  # default 'newest'
        books_qs = books_qs.order_by('-created_at')

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(books_qs, 36)
    total_count = paginator.count
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return page_obj, query, sort_by, total_count


def books_by_author_view(request, pk):
    """Filter books by author with search and sorting."""
    author = get_object_or_404(Author, pk=pk)
    books_qs = Book.objects.filter(author=author, is_upcoming=False).select_related(
        'author', 'publication', 'category'
    )
    page_obj, query, sort_by, total_count = _filter_and_sort_books(books_qs, request)

    context = {
        'books': page_obj,
        'filter_type': 'author',
        'filter_obj': author,
        'query': query,
        'sort_by': sort_by,
        'total_count': total_count,
        'page_title': f'Books by {author.name}',
    }
    return render(request, 'catalog/filtered_books.html', context)


def books_by_publication_view(request, pk):
    """Filter books by publication with search and sorting."""
    publication = get_object_or_404(Publication, pk=pk)
    books_qs = Book.objects.filter(publication=publication, is_upcoming=False).select_related(
        'author', 'publication', 'category'
    )
    page_obj, query, sort_by, total_count = _filter_and_sort_books(books_qs, request)

    context = {
        'books': page_obj,
        'filter_type': 'publication',
        'filter_obj': publication,
        'query': query,
        'sort_by': sort_by,
        'total_count': total_count,
        'page_title': f'Books from {publication.name}',
    }
    return render(request, 'catalog/filtered_books.html', context)


def books_by_category_view(request, slug):
    """Filter books by category with search and sorting."""
    category = get_object_or_404(Category, slug=slug)
    books_qs = Book.objects.filter(category=category, is_upcoming=False).select_related(
        'author', 'publication', 'category'
    )
    page_obj, query, sort_by, total_count = _filter_and_sort_books(books_qs, request)

    context = {
        'books': page_obj,
        'filter_type': 'category',
        'filter_obj': category,
        'query': query,
        'sort_by': sort_by,
        'total_count': total_count,
        'page_title': f'{category.name} Books',
    }
    return render(request, 'catalog/filtered_books.html', context)


def authors_view(request):
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'books_desc')

    authors = Author.objects.annotate(num_books=Count('books'))

    if query:
        authors = authors.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if sort_by == 'alpha_asc':
        authors = authors.order_by('name')
    elif sort_by == 'alpha_desc':
        authors = authors.order_by('-name')
    elif sort_by == 'books_asc':
        authors = authors.order_by('num_books', 'name')
    elif sort_by == 'newest':
        authors = authors.order_by('-created_at')
    else:  # default 'books_desc' (most books first)
        sort_by = 'books_desc'
        authors = authors.order_by('-num_books', 'name')

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(authors, 24)
    total_count = paginator.count
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'catalog/authors.html', {
        'authors': page_obj,
        'query': query,
        'sort_by': sort_by,
        'total_count': total_count,
        'page_title': 'Authors',
    })


def publications_view(request):
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'books_desc')

    publications = Publication.objects.annotate(num_books=Count('books'))

    if query:
        publications = publications.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if sort_by == 'alpha_asc':
        publications = publications.order_by('name')
    elif sort_by == 'alpha_desc':
        publications = publications.order_by('-name')
    elif sort_by == 'books_asc':
        publications = publications.order_by('num_books', 'name')
    elif sort_by == 'newest':
        publications = publications.order_by('-created_at')
    else:  # default 'books_desc' (most books first)
        sort_by = 'books_desc'
        publications = publications.order_by('-num_books', 'name')

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(publications, 24)
    total_count = paginator.count
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'catalog/publications.html', {
        'publications': page_obj,
        'query': query,
        'sort_by': sort_by,
        'total_count': total_count,
        'page_title': 'Publications',
    })


def categories_view(request):
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'books_desc')

    categories = Category.objects.annotate(num_books=Count('books'))

    if query:
        categories = categories.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if sort_by == 'alpha_asc':
        categories = categories.order_by('name')
    elif sort_by == 'alpha_desc':
        categories = categories.order_by('-name')
    elif sort_by == 'books_asc':
        categories = categories.order_by('num_books', 'name')
    else:  # default 'books_desc' (most books first)
        sort_by = 'books_desc'
        categories = categories.order_by('-num_books', 'name')

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(categories, 24)
    total_count = paginator.count
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'catalog/categories.html', {
        'categories': page_obj,
        'query': query,
        'sort_by': sort_by,
        'total_count': total_count,
        'page_title': 'Categories',
    })


def request_book_view(request):
    """User facing page to request books that are not in the catalog."""
    if request.method == 'POST':
        if is_throttled(request, 'book_request', per_ip_limit=5, global_limit=50, window=3600):
            messages.error(request, "Too many book requests submitted recently. Please try again later.")
            return redirect('request_book')

        name = request.POST.get('name', '').strip()[:150]
        address = request.POST.get('address', '').strip()[:500]
        phone = request.POST.get('phone', '').strip()[:20]
        email = request.POST.get('email', '').strip()[:254]

        titles = request.POST.getlist('book_title[]')[:10]
        authors = request.POST.getlist('author[]')[:10]
        publications = request.POST.getlist('publication[]')[:10]
        quantities = request.POST.getlist('quantity[]')[:10]

        if not name or not phone:
            messages.error(request, "Name and Phone number are required.")
            return redirect('request_book')

        valid_items = any(t.strip() for t in titles)
        if not valid_items:
            messages.error(request, "Please enter at least one book title.")
            return redirect('request_book')

        # Create main request
        book_req = BookRequest.objects.create(
            user=request.user if request.user.is_authenticated else None,
            name=name,
            address=address,
            phone=phone,
            email=email
        )

        # Create request items in bulk (1 query instead of N queries)
        items_to_create = []
        for i in range(len(titles)):
            title = titles[i].strip()[:250]
            if not title:
                continue

            author_val = authors[i].strip()[:200] if i < len(authors) else ''
            pub_val = publications[i].strip()[:200] if i < len(publications) else ''
            qty_val = 1
            if i < len(quantities):
                try:
                    qty_val = int(quantities[i])
                    if qty_val <= 0 or qty_val > 100:
                        qty_val = 1
                except ValueError:
                    qty_val = 1

            items_to_create.append(
                BookRequestItem(
                    request=book_req,
                    book_title=title,
                    author=author_val,
                    publication=pub_val,
                    quantity=qty_val
                )
            )
        if items_to_create:
            BookRequestItem.objects.bulk_create(items_to_create)

        # Notify admin
        from youth_club_library.notifications import notify_admin_new_book_request
        notify_admin_new_book_request(book_req)

        context = {
            'page_title': 'Request Submitted',
            'success': True,
            'customer_name': name,
        }
        return render(request, 'catalog/request_book.html', context)

    context = {
        'page_title': 'Request a Book',
        'success': False,
    }
    return render(request, 'catalog/request_book.html', context)


def join_waitlist(request, pk):
    """View for users to join the waitlist for an out-of-stock book."""
    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to join the waitlist.")
        return redirect('account_login')
        
    book = get_object_or_404(Book, pk=pk)
    
    if book.is_in_stock:
        messages.info(request, "This book is already in stock.")
        return redirect('book_detail', pk=pk)
        
    WaitlistEntry.objects.get_or_create(user=request.user, book=book)
    messages.success(request, f"You have been added to the waitlist for '{book.title}'. We will email you when it's back in stock.")
    return redirect('book_detail', pk=pk)


def robots_txt_view(request):
    """Dynamic robots.txt pointing to canonical sitemap and protecting private routes."""
    from django.http import HttpResponse
    sitemap_url = "https://www.youthclublibrary.com/sitemap.xml"
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /about/",
        "Allow: /books/",
        "Allow: /authors/",
        "Allow: /publications/",
        "Allow: /categories/",
        "Allow: /membership/",
        "",
        "Disallow: /admin/",
        "Disallow: /admin-panel/",
        "Disallow: /accounts/",
        "Disallow: /orders/",
        "Disallow: /waitlist/",
        "Disallow: /*?*q=*",
        "",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def google_verification_view(request, code):
    """Serve Google Search Console HTML verification file."""
    from django.http import HttpResponse
    return HttpResponse(f"google-site-verification: google{code}.html\n", content_type="text/html")
