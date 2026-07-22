# Youth Club Library 📚

A full-stack Django e-commerce and library management system.

---

> ⚠️ **SECURITY NOTICE — GIT HISTORY**
> If any secrets (API keys, passwords, database URLs) were ever committed to this repository's git history, **those values are permanently visible in old commits** even after removal.
> **Action required:** Immediately rotate/regenerate the following credentials if they appeared in any past commit:
> - Django `SECRET_KEY`
> - Google OAuth `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
> - Gmail App Password (`EMAIL_HOST_PASSWORD`)
> - Neon PostgreSQL `DATABASE_URL` (password)
> - ScraperAPI `SCRAPER_API_KEY`
> - Any Cloudinary API credentials
>
> Generate new values from their respective platforms and update your environment variables on Render.

---

## Quick Start

### 1. Create & activate virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
copy .env.example .env    # Windows
cp .env.example .env      # macOS/Linux
# Edit .env with your values (SECRET_KEY, Google OAuth, etc.)
```

### 4. Run migrations
```bash
python manage.py makemigrations accounts catalog orders
python manage.py migrate
```

### 5. Create superuser
```bash
python manage.py createsuperuser
```

### 6. Start the development server
```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000

## Admin Panel
http://127.0.0.1:8000/admin/

Use the admin panel to:
- Add **MembershipPlans** (with JSON characteristics)
- Add **Authors**, **Publications**, **Categories**
- Add **Books** (mark as Featured / New / Upcoming)
- **Activate memberships** — select pending memberships → Actions → Activate
- **Mark orders as Paid** — select orders → Actions → Mark as Paid

## Google OAuth Setup (Optional)
1. Go to https://console.cloud.google.com/
2. Create a project → APIs & Services → Credentials
3. Create OAuth 2.0 Client ID (Web application)
4. Add redirect URI: `http://127.0.0.1:8000/accounts/google/login/callback/`
5. Copy Client ID and Secret to `.env`
6. In Django admin: Sites → edit `example.com` to `127.0.0.1:8000`
7. Social Applications → Add → Google → fill in Client ID/Secret → select site

## Sample MembershipPlan JSON characteristics
```json
[
  "Borrow up to 3 books simultaneously",
  "Priority access to new arrivals",
  "5% discount on all purchases",
  "Free delivery to selected points",
  "Member-only events access"
]
```

## Project Structure
```
youth_club_library/
├── accounts/         ← CustomUser, MembershipPlan, UserMembership
├── catalog/          ← Author, Publication, Category, Book, BookReview
├── orders/           ← Order (Buy/Borrow)
├── templates/        ← All HTML templates
│   ├── base.html
│   ├── home.html
│   ├── account/      ← Allauth login/signup
│   ├── accounts/     ← Dashboard, membership
│   ├── catalog/      ← Books, book detail, filters
│   ├── orders/       ← Checkout, success
│   └── partials/     ← Reusable components
└── youth_club_library/ ← Settings, urls, wsgi
```

## Technology Stack
- **Backend**: Django 4.2 + SQLite
- **Auth**: Django Allauth (email login + Google OAuth)
- **Frontend**: Tailwind CSS CDN + Alpine.js CDN
- **Scraping**: BeautifulSoup4 + requests (cached 24h)
