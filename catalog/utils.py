
import logging
import requests
import re
import hashlib
from decouple import config
from bs4 import BeautifulSoup
from django.core.cache import cache

logger = logging.getLogger(__name__)

SCRAPER_API_KEY = config('SCRAPER_API_KEY', default=None)

def _get_page(url: str, headers: dict = None, render: bool = False, premium: bool = False) -> requests.Response:
    if SCRAPER_API_KEY:
        payload = {'api_key': SCRAPER_API_KEY, 'url': url}
        
        # Tell ScraperAPI to forward your custom User-Agent
        if headers:
            payload['keep_headers'] = 'true'
            
        # Tell ScraperAPI to wait and execute Javascript (Solves Cloudflare challenges)
        if render:
            payload['render'] = 'true'
            
        # Optional: Use ScraperAPI's Premium Residential IPs
        if premium:
            payload['premium'] = 'true'

        req_headers = headers if headers else {}
        # Increased timeout because JS rendering takes longer
        return requests.get('https://api.scraperapi.com/', params=payload, headers=req_headers, timeout=30)
    else:
        import cloudscraper
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        return scraper.get(url, headers=headers or {}, timeout=15)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
}
TIMEOUT = 8  # seconds


def _is_related(scraped_name: str, query: str) -> bool:
    """Check if the scraped book title is related to the query title."""
    words = [w.strip() for w in re.split(r'[\s\-\,\.\?\:\!]+', query) if len(w.strip()) > 1]
    if not words:
        return True
    scraped_lower = scraped_name.lower()
    return any(w.lower() in scraped_lower for w in words)


def _scrape_rokomari(title: str) -> dict | None:
    """Scrape Rokomari.com for book price."""
    try:
        query = title.replace(' ', '+')
        url = f'https://www.rokomari.com/search?term={query}'
        
        resp = _get_page(url, headers=HEADERS)
        
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, 'html.parser')

        # First result card
        card = soup.select_one('.books-wrapper__item, .product-card-wrapper, .product-card, .book-list-single-book-item')
        if not card:
            return None

        price_tag = card.select_one('.book-price, .product-card__price, .price')
        name_tag = card.select_one('.book-title, .product-card__title, .book-title a')
        link_tag = card.select_one('a[href]')

        book_name = name_tag.get_text(strip=True) if name_tag else title
        if not _is_related(book_name, title):
            return None

        price_text = None
        if price_tag:
            strike = price_tag.select_one('strike')
            if strike:
                price_text = price_tag.get_text(strip=True).replace(strike.get_text(strip=True), '').strip()
            else:
                price_text = price_tag.get_text(strip=True)
        
        if link_tag and link_tag['href'].startswith('/'):
            link = 'https://www.rokomari.com' + link_tag['href']
        elif link_tag:
            link = link_tag['href']
        else:
            link = url

        return {
            'site': 'Rokomari',
            'price': price_text,
            'book_name': book_name,
            'url': link,
        }
    except Exception as exc:
        logger.warning('Rokomari scrape failed for "%s": %s', title, exc)
        return None


def get_competitor_prices(book_title: str, cache_ttl: int = 86400) -> list[dict]:
    """
    Return a list of competitor price results. Cached for 24 hours.
    """
    hashed = hashlib.md5(book_title.encode('utf-8')).hexdigest()
    cache_key = f'competitor_prices:{hashed}'
    cached = cache.get(cache_key)
    
    if cached is not None:
        return cached

    results = []
    
    # 1. Rokomari
    rok_result = _scrape_rokomari(book_title)
    if rok_result:
        results.append(rok_result)
    else:
        results.append({'site': 'Rokomari', 'price': None, 'url': '#'})

    # Save to cache
    cache.set(cache_key, results, cache_ttl)
    return results