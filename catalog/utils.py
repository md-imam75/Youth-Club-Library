
import logging
import requests
import re
import hashlib
from decouple import config
from bs4 import BeautifulSoup
from django.core.cache import cache

logger = logging.getLogger(__name__)

SCRAPER_API_KEY = config('SCRAPER_API_KEY', default=None)

def _get_page(url: str, headers: dict = None) -> requests.Response:
    if SCRAPER_API_KEY:
        payload = {'api_key': SCRAPER_API_KEY, 'url': url}
        if headers:
            payload['keep_headers'] = 'true'
            return requests.get('https://api.scraperapi.com/', params=payload, headers=headers, timeout=20)
        return requests.get('https://api.scraperapi.com/', params=payload, timeout=20)
    else:
        import cloudscraper
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        return scraper.get(url, headers=headers or {}, timeout=10)

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
        
        resp = _get_page(url)
        
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


# def _scrape_wafilife(title: str) -> dict | None:
#     """Scrape Wafilife.com for book price using Next.js RSC component stream parsing."""
#     try:
#         query = title.replace(' ', '+')
#         url = f'https://www.wafilife.com/?s={query}&post_type=product'
        
#         rsc_headers = dict(HEADERS)
#         rsc_headers['RSC'] = '1'
        
#         resp = requests.get(url, headers=rsc_headers, timeout=TIMEOUT)
#         resp.raise_for_status()
        
#         content = resp.content
#         pattern = rb'\{\"product\"\:\{\"id\"\:\"(?P<id>\d+)\",\"PID\"\:\"(?P<pid>\d+)\",\"name\"\:\"(?P<name>[^\"]+)\",\"slug\"\:\"(?P<slug>[^\"]+)\".*?\"price\"\:?(?P<price>\d+).*?\"productUrl\"\:\"(?P<url>[^\"]+)\"'
        
#         matches = list(re.finditer(pattern, content))
#         if not matches:
#             return None
            
#         # Find the first matching product that is related to the title
#         matched_result = None
#         for m in matches:
#             name_bytes = m.group('name')
#             name_str = name_bytes.decode('utf-8', errors='ignore')
            
#             if '\\u' in name_str:
#                 try:
#                     decoded_raw = name_str.encode('utf-8').decode('unicode_escape')
#                     name_str = decoded_raw.encode('latin1').decode('utf-8')
#                 except Exception:
#                     pass
            
#             if _is_related(name_str, title):
#                 price_bytes = m.group('price')
#                 url_bytes = m.group('url')
#                 price_str = price_bytes.decode('utf-8', errors='ignore')
#                 url_str = url_bytes.decode('utf-8', errors='ignore')
                
#                 matched_result = {
#                     'site': 'Wafilife',
#                     'price': f'TK. {price_str}' if price_str else None,
#                     'book_name': name_str,
#                     'url': f'https://www.wafilife.com{url_str}',
#                 }
#                 break
def _scrape_wafilife(title: str) -> dict | None:
    """Scrape Wafilife.com for book price using standard HTML parsing."""
    try:
        query = title.replace(' ', '+')
        url = f'https://www.wafilife.com/?s={query}&post_type=product'
        
        resp = _get_page(url)
        
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.select('.product, .product-item, .product-wrapper')
        
        for card in cards:
            title_tag = card.select_one('.woocommerce-loop-product__title, h3 a, h2, .heading-title a')
            link_tag = card.select_one('a')
            
            if not title_tag or not link_tag:
                continue
                
            book_name = title_tag.get_text(strip=True)
            
            if _is_related(book_name, title):
                price_tag = card.select_one('ins .woocommerce-Price-amount, .price .woocommerce-Price-amount, .price')
                
                price_text = price_tag.get_text(strip=True) if price_tag else None
                
                if price_text:
                    price_text = price_text.replace('৳', 'TK. ').replace('Tk', 'TK. ')
                
                return {
                    'site': 'Wafilife',
                    'price': price_text,
                    'book_name': book_name,
                    'url': link_tag.get('href', url)
                }
                
        return None
    except Exception as exc:
        logger.warning('Wafilife scrape failed: %s', exc)
        return None
    
def _scrape_niyamahshop(title: str) -> dict | None:
    """Scrape Niyamahshop.com using standard WooCommerce HTML parsing."""
    try:
        query = title.replace(' ', '+')
        url = f'https://www.niyamahshop.com/?s={query}&post_type=product'
        
        resp = _get_page(url)
        
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.select('.product, .product-item, li.product')
        
        for card in cards:
            title_tag = card.select_one('.woocommerce-loop-product__title, h2, h3, .product-title')
            link_tag = card.select_one('a.woocommerce-LoopProduct-link, a')
            
            if not title_tag or not link_tag:
                continue
                
            book_name = title_tag.get_text(strip=True)
            
            if _is_related(book_name, title):
                price_tag = card.select_one('.price')
                price_text = None
                
                if price_tag:
                    ins_tag = price_tag.select_one('ins')
                    if ins_tag:
                        amount_span = ins_tag.select_one('.woocommerce-Price-amount')
                        price_text = amount_span.get_text(strip=True) if amount_span else ins_tag.get_text(strip=True)
                    else:
                        amount_span = price_tag.select_one('.woocommerce-Price-amount')
                        price_text = amount_span.get_text(strip=True) if amount_span else price_tag.get_text(strip=True)
                
                if price_text:
                    price_text = price_text.replace('Current price is:', '').replace('Original price was:', '')
                    price_text = price_text.replace('৳', 'TK. ').replace('Tk', 'TK. ').strip()
                
                return {
                    'site': 'Niyamah Shop',
                    'price': price_text,
                    'book_name': book_name,
                    'url': link_tag.get('href', url)
                }
                
        return None
    except Exception as exc:
        logger.warning('Niyamah Shop scrape failed: %s', exc)
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

    # 2. Wafilife (Restored Next.js RSC parser which bypasses blocks)
    waf_result = _scrape_wafilife(book_title)
    if waf_result:
        results.append(waf_result)
    else:
        results.append({'site': 'Wafilife', 'price': None, 'url': '#'})

    # 3. Niyamah Shop
    niyamah_result = _scrape_niyamahshop(book_title)
    if niyamah_result:
        results.append(niyamah_result)
    else:
        results.append({'site': 'Niyamah Shop', 'price': None, 'url': '#'})

    # Save to cache
    cache.set(cache_key, results, cache_ttl)
    return results