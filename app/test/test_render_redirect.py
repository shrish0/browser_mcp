import sys
import os
import traceback

# Add the 'app' directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scraper import WebScraper
from exceptions import RedirectError, NotFoundError

def test_url_redirect():
    url = "https://dashboard.render.com/web/srv-d78n3togjchc73f4u7b0/deploys/dep-d7922vmdqaus73dao7sg?r=2026-04-05%4008%3A45%3A54%7E2026-04-05%4008%3A49%3A28"
    
    scraper = WebScraper()
    print(f"Testing URL: {url}")
    
    try:
        # First, try static scraping
        print("\n--- Try Static Scrape ---")
        result = scraper.scrape_static(url)
        print("Static scrape succeeded without exception. URL didn't redirect or redirect wasn't caught!")
        
    except RedirectError as e:
        print(f"Success! Caught RedirectError in static scrape: {e.error_message}")
        print(f"Redirected to: {e.details.get('redirect_url')}")
    except NotFoundError as e:
        print(f"Success! Caught NotFoundError in static scrape: {e.error_message}")
    except Exception as e:
        print(f"Caught other exception in static scrape: {type(e).__name__}: {e}")
        traceback.print_exc()

    try:
        # Second, try dynamic scraping
        print("\n--- Try Dynamic Scrape ---")
        result = scraper.scrape_dynamic(url)
        print("Dynamic scrape succeeded without exception. URL didn't redirect or redirect wasn't caught!")
        
    except RedirectError as e:
        print(f"Success! Caught RedirectError in dynamic scrape: {e.error_message}")
        print(f"Redirected to: {e.details.get('redirect_url')}")
    except NotFoundError as e:
        print(f"Success! Caught NotFoundError in dynamic scrape: {e.error_message}")
    except Exception as e:
        print(f"Caught other exception in dynamic scrape: {type(e).__name__}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_url_redirect()
