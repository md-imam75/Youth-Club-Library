<div align="center">

# 📚 Youth Club Library

**Browse. Borrow. Purchase.**

A modern, full-stack digital library and e-commerce platform built with Django — featuring book browsing, membership-based borrowing, online purchasing, and a powerful admin panel.

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-youthclublibrary.com-0ea5e9?style=for-the-badge)](https://www.youthclublibrary.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![License](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)](LICENSE)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🛍️ For Customers
- 📖 Browse, search & filter books by category, author, publication
- 🛒 Full shopping cart with multi-item checkout
- 💳 bKash & offline payment support
- 📦 Multiple delivery options with real-time cost calculation
- 🔖 Membership plans — borrow books for free
- ⭐ Book reviews & ratings
- 📊 Competitor price comparison (auto-scraped)
- 📥 Downloadable PDF invoices
- 📋 Custom book request system
- 🔐 Email + Google OAuth login

</td>
<td width="50%">

### ⚙️ For Admins
- 📈 Dashboard with revenue analytics & stats
- 📚 Full CRUD for Books, Authors, Publications, Categories
- 👥 User & membership management
- 🧾 Order management (approve, deliver, cancel)
- 🏪 Offline billing / POS system for walk-in customers
- 📧 Automated invoice emails on payment approval
- 📊 Sales reports with PDF export
- 💬 Testimonials management
- 🔗 Social media links manager
- 🚚 Configurable delivery options

</td>
</tr>
</table>

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Django 4.2+, Python 3.10+ |
| **Database** | PostgreSQL (Neon) — SQLite for local dev |
| **Authentication** | Django Allauth (Email + Google OAuth 2.0) |
| **Frontend** | Tailwind CSS (CDN) + Alpine.js |
| **Media Storage** | Cloudinary (production) |
| **Static Files** | WhiteNoise (compressed & cached) |
| **PDF Generation** | xhtml2pdf with Bangla font support |
| **Price Scraping** | BeautifulSoup4 + ScraperAPI (cached 24h) |
| **Hosting** | Render (Web Service + PostgreSQL) |
| **Domain** | [youthclublibrary.com](https://www.youthclublibrary.com) |

---

## 📁 Project Structure

```
youth_club_library/
├── accounts/              # CustomUser model, Membership, Profile
│   ├── models.py          # CustomUser, MembershipPlan, UserMembership
│   ├── views.py           # Dashboard, membership, account deletion
│   └── forms.py           # Signup, profile update, membership forms
├── catalog/               # Book catalog & browsing
│   ├── models.py          # Book, Author, Publication, Category, Review
│   ├── views.py           # Book listing, detail, search, filters
│   └── utils.py           # Competitor price scraping engine
├── orders/                # Shopping cart & checkout
│   ├── models.py          # Order, OfflineBill, DeliveryOption
│   └── views.py           # Cart, checkout, borrow, invoices
├── panel/                 # Custom admin panel (staff-only)
│   └── views.py           # Dashboard, CRUD, reports, billing
├── templates/             # All HTML templates
│   ├── base.html          # Master layout with navbar & footer
│   ├── home.html          # Landing page with carousels
│   ├── account/           # Allauth login/signup templates
│   ├── accounts/          # Dashboard, membership, delete account
│   ├── catalog/           # Books grid, book detail, authors
│   ├── orders/            # Cart, checkout, invoices
│   └── admin_panel/       # Staff admin panel templates
├── static/                # CSS, JS, images, fonts
├── youth_club_library/    # Project settings & config
│   ├── settings.py        # Django settings (env-var driven)
│   ├── urls.py            # Root URL configuration
│   └── context_processors.py
├── .env.example           # Environment variable template
├── build.sh               # Render deployment script
├── requirements.txt       # Python dependencies
└── manage.py
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- pip
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/md-imam75/Youth-Club-Library.git
cd Youth-Club-Library
```

### 2. Create & Activate Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```
Open `.env` and fill in your values. See [`.env.example`](.env.example) for all required variables and instructions.

### 5. Run Database Migrations
```bash
python manage.py makemigrations accounts catalog orders
python manage.py migrate
```

### 6. Create a Superuser
```bash
python manage.py createsuperuser
```

### 7. Start the Development Server
```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000** 🎉

---

## 🔐 Google OAuth Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → **APIs & Services** → **Credentials**
3. Create an **OAuth 2.0 Client ID** (Web Application)
4. Add Authorized redirect URI:
   ```
   http://127.0.0.1:8000/accounts/google/login/callback/
   ```
   For production, also add:
   ```
   https://www.youthclublibrary.com/accounts/google/login/callback/
   ```
5. Copy **Client ID** and **Client Secret** to your `.env` file
6. Run the setup command:
   ```bash
   python manage.py setup_social
   ```

---

## 🔧 Admin Panel

Access the custom admin panel at `/admin-panel/` (staff accounts only).

| Feature | Description |
|---|---|
| **Dashboard** | Revenue, order stats, recent activity overview |
| **Books** | Add/edit/delete books with cover images, pricing, discounts |
| **Orders** | Approve payments, mark delivered, cancel with stock restore |
| **Memberships** | Review and activate member applications |
| **Billing** | Create walk-in bills for offline customers |
| **Reports** | Generate sales reports with PDF download |
| **Users** | View user profiles, order history, membership status |

---

## 🌐 Deployment (Render)

This project is production-ready for [Render](https://render.com):

1. Connect your GitHub repository to Render
2. Set **Build Command**: `./build.sh`
3. Set **Start Command**: `gunicorn youth_club_library.wsgi:application`
4. Add all environment variables from `.env.example` to Render's Environment tab
5. Render will auto-deploy on every push to `main`

---

## 🔒 Security

- All secrets loaded via environment variables (`python-decouple`)
- No hardcoded credentials in source code
- HTTPS enforced in production (`SECURE_SSL_REDIRECT`)
- Session & CSRF cookies secured with `HttpOnly`, `Secure`, and `SameSite=Lax`
- Login brute-force protection (5 attempts → 5 min lockout)
- Server-side role enforcement on all admin endpoints (`@staff_required`)
- IDOR protection — ownership verified on all user-specific data access
- Django ORM parameterized queries (SQL injection safe)
- Auto-escaped templates (XSS safe)
- Account deletion flow for user data privacy

> ⚠️ **Git History Notice:** If any secrets were previously committed to this repository, those values remain in git history. Always rotate credentials after exposure — see [`.env.example`](.env.example) for the full list of secrets to manage.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ for the Youth Club community**

[Live Site](https://www.youthclublibrary.com) · [Report Bug](https://github.com/md-imam75/Youth-Club-Library/issues) · [Request Feature](https://github.com/md-imam75/Youth-Club-Library/issues)

</div>
