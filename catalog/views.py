from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count
from .models import Author, Publication, Category, Book, BookReview, BookRequest, BookRequestItem, WaitlistEntry, SiteTestimonial
from accounts.models import CustomUser, UserMembership, MembershipPlan


def home_view(request):
    """Home page: hero, carousels, counters, CTA."""
    featured_books = Book.objects.filter(is_featured=True, is_upcoming=False).select_related(
        'author', 'publication'
    )[:12]
    new_books = Book.objects.filter(is_new=True, is_upcoming=False).select_related(
        'author', 'publication'
    )[:12]
    upcoming_books = Book.objects.filter(is_upcoming=True).select_related(
        'author', 'publication'
    )[:12]
  
    # Statistics for animated counters
    total_members = UserMembership.objects.filter(status='Active').count()
    total_books = Book.objects.filter(is_upcoming=False).count()
    total_authors = Author.objects.count()
    total_categories = Category.objects.count()

    # Active testimonials & membership plans
    testimonials = SiteTestimonial.objects.filter(is_active=True)
    plans = MembershipPlan.objects.filter(is_active=True)

    context = {
        'featured_books': featured_books,
        'new_books': new_books,
        'upcoming_books': upcoming_books,
        'total_members': total_members,
        'total_books': total_books,
        'total_authors': total_authors,
        'total_categories': total_categories,
        'testimonials': testimonials,
        'plans': plans,
        'page_title': 'Home',
    }
    return render(request, 'home.html', context) 


def about_view(request):
    """About Us page."""
    context = {
        'page_title': 'About Us',
    }
    return render(request, 'catalog/about.html', context) 



def books_view(request):
    """All books grid with search."""
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'newest')

    books = Book.objects.select_related('author', 'publication', 'category').filter(is_upcoming=False)

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

    # Compute max price across ALL books (before price filter) for the slider ceiling
    max_price_val = Book.objects.filter(is_upcoming=False).annotate(
        effective_price=Coalesce('offer_price', 'regular_price')
    ).aggregate(max_p=Max('effective_price'))['max_p'] or 0
    # Round up to nearest 100 for a clean slider max
    import math
    slider_max = int(math.ceil(max_price_val / 100) * 100) if max_price_val else 5000

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
        books = books.annotate(sales_count=Count('orders')).order_by('-sales_count', '-created_at')
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
        # Leave as default order (if searched) or fallback to newest
        if not query:
            books = books.order_by('-created_at')
    else:
        # Default to newest (date_desc)
        books = books.order_by('-created_at')
    total_count = books.count()

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(books, 36)
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
    """Book detail: competitor prices, Buy/Borrow buttons, reviews."""
    book = get_object_or_404(
        Book.objects.select_related('author', 'publication', 'category'),
        pk=pk
    )
    reviews = book.reviews.select_related('user').all()

    # Competitor prices scraping removed for performance

    # Handle review submission
    user_review = None
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()

        if request.method == 'POST' and 'submit_review' in request.POST:
            if user_review:
                messages.warning(request, 'You have already reviewed this book.')
            else:
                rating = request.POST.get('rating')
                review_text = request.POST.get('review_text', '').strip()
                if rating and review_text:
                    BookReview.objects.create(
                        user=request.user,
                        book=book,
                        rating=int(rating),
                        review_text=review_text,
                    )
                    messages.success(request, 'Your review has been submitted. Thank you!')
                    return redirect('book_detail', pk=book.pk)
                else:
                    messages.error(request, 'Please provide a rating and review text.')

    # Related books by Category, Author, and Publication
    related_category_books = Book.objects.filter(
        category=book.category, is_upcoming=False
    ).exclude(pk=book.pk).select_related('author')[:6]

    related_author_books = Book.objects.filter(
        author=book.author, is_upcoming=False
    ).exclude(pk=book.pk).select_related('author')[:6] if book.author else []

    related_publication_books = Book.objects.filter(
        publication=book.publication, is_upcoming=False
    ).exclude(pk=book.pk).select_related('author')[:6] if book.publication else []

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
        books_qs = books_qs.annotate(sales_count=Count('orders')).order_by('-sales_count', '-created_at')
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

    total_count = books_qs.count()

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(books_qs, 36)
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
    sort_by = request.GET.get('sort', 'alpha_asc')

    authors = Author.objects.annotate(num_books=Count('books'))

    if query:
        authors = authors.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if sort_by == 'alpha_desc':
        authors = authors.order_by('-name')
    elif sort_by == 'books_desc':
        authors = authors.order_by('-num_books', 'name')
    elif sort_by == 'books_asc':
        authors = authors.order_by('num_books', 'name')
    elif sort_by == 'newest':
        authors = authors.order_by('-created_at')
    else:  # default 'alpha_asc'
        authors = authors.order_by('name')

    total_count = authors.count()

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(authors, 24)
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
    sort_by = request.GET.get('sort', 'alpha_asc')

    publications = Publication.objects.annotate(num_books=Count('books'))

    if query:
        publications = publications.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if sort_by == 'alpha_desc':
        publications = publications.order_by('-name')
    elif sort_by == 'books_desc':
        publications = publications.order_by('-num_books', 'name')
    elif sort_by == 'books_asc':
        publications = publications.order_by('num_books', 'name')
    elif sort_by == 'newest':
        publications = publications.order_by('-created_at')
    else:  # default 'alpha_asc'
        publications = publications.order_by('name')

    total_count = publications.count()

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(publications, 24)
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
    sort_by = request.GET.get('sort', 'alpha_asc')

    categories = Category.objects.annotate(num_books=Count('books'))

    if query:
        categories = categories.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if sort_by == 'alpha_desc':
        categories = categories.order_by('-name')
    elif sort_by == 'books_desc':
        categories = categories.order_by('-num_books', 'name')
    elif sort_by == 'books_asc':
        categories = categories.order_by('num_books', 'name')
    else:  # default 'alpha_asc'
        categories = categories.order_by('name')

    total_count = categories.count()

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(categories, 24)
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
        name = request.POST.get('name')
        address = request.POST.get('address', '')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')

        titles = request.POST.getlist('book_title[]')
        authors = request.POST.getlist('author[]')
        publications = request.POST.getlist('publication[]')
        quantities = request.POST.getlist('quantity[]')

        if not name or not phone:
            messages.error(request, "Name and Phone number are required.")
            return redirect('request_book')

        valid_items = False
        for title in titles:
            if title.strip():
                valid_items = True
                break

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

        # Create request items
        for i in range(len(titles)):
            title = titles[i].strip()
            if not title:
                continue

            author_val = authors[i].strip() if i < len(authors) else ''
            pub_val = publications[i].strip() if i < len(publications) else ''
            qty_val = 1
            if i < len(quantities):
                try:
                    qty_val = int(quantities[i])
                    if qty_val <= 0:
                        qty_val = 1
                except ValueError:
                    qty_val = 1

            BookRequestItem.objects.create(
                request=book_req,
                book_title=title,
                author=author_val,
                publication=pub_val,
                quantity=qty_val
            )

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
