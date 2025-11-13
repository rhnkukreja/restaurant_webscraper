import re
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ---------- Configuration ----------
DEFAULT_WAIT = 12
SCROLL_ATTEMPTS = 3
NEGATIVE_REVIEW_LIMIT = 10

# Centralize selectors to make maintenance easier
SELECTORS = {
    "name": ["h1.DUwDvf", "h1.fontHeadlineLarge", "h1"],
    "rating": ['div.F7nice span[aria-hidden="true"]', 'span.ceNzKf[aria-hidden="true"]'],
    "review_count_buttons": ['div.F7nice button[aria-label*="reviews"]', 'button[aria-label*="reviews"]', 'button[aria-label*="review"]'],
    "address_button": 'button[data-item-id="address"]',
    "phone_buttons": ['button[data-item-id*="phone"]', 'button[aria-label*="Phone"]'],
    "website_link": 'a[data-item-id="authority"]',
    "reviews_tab_buttons": [
        (By.XPATH, '//button[contains(@aria-label, "Reviews")]'),
        (By.XPATH, '//button[contains(@aria-label, "reviews")]'),
        (By.CSS_SELECTOR, 'button[aria-label*="review"]'),
    ],
    "sort_buttons": [
        (By.XPATH, '//button[contains(@aria-label, "Sort reviews")]'),
        (By.CSS_SELECTOR, 'button[aria-label*="Sort"]'),
    ],
    "lowest_option": [
        (By.XPATH, '//div[@role="menuitemradio" and contains(., "Lowest")]'),
        (By.XPATH, '//div[@role="menuitemradio" and contains(., "lowest")]'),
    ],
    "scrollable": ['div.m6QErb.DxyBCb.kA9KIf.dS8AEf', 'div.m6QErb', 'div[role="main"]'],
    "review_containers": ['div.jftiEf', 'div.WMbnJf', 'div[data-review-id]'],
    "expand_buttons": ['button.w8nwRe'],
    "review_text": ['span.wiI7pd', 'span.MyEned', 'div.MyEned'],
    "review_date": ['span.rsqaWe', 'span.DU9Pgb'],
    "rating_icon": 'span[role="img"][aria-label]'
}

# ---------- Utility helpers ----------
def _safe_find_text(driver, css_or_selector, by=By.CSS_SELECTOR, timeout=3) -> Optional[str]:
    try:
        if by == By.CSS_SELECTOR:
            el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, css_or_selector)))
        else:
            el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, css_or_selector)))
        txt = el.text.strip()
        return txt if txt else None
    except:
        return None

def _safe_find_element(driver, by, selector, timeout=3):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except:
        return None

def _attr_or_none(element, attr_name):
    try:
        return element.get_attribute(attr_name)
    except:
        return None

def _parse_int_from_aria(aria_text: str) -> Optional[int]:
    if not aria_text:
        return None
    m = re.search(r'([\d,]+)\s*review', aria_text, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(',', ''))
    return None

def _parse_date_ago_text(date_str: str) -> Optional[int]:
    # Returns number of years if "X years ago" pattern found, else None
    if not date_str:
        return None
    m = re.search(r'(\d+)\s+years?', date_str, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

# ---------- Main extractor ----------
class GoogleMapsExtractorA:
    def __init__(self, headless: bool = True):
        self.driver = None
        self.wait = None
        self.headless = headless

    def _setup_driver(self):
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        service = Service(ChromeDriverManager().install(), log_path=os.devnull)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, DEFAULT_WAIT)

    def _close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def get_place_details(self, url: str) -> Dict:
        result = {
            'name': None,
            'address': None,
            'rating': None,
            'total_reviews': 0,
            'phone': None,
            'website': None,
            'first_review_date': None,
            'recent_negative_reviews': []
        }

        try:
            print("→ Starting browser")
            self._setup_driver()
            print("→ Loading page")
            self.driver.get(url)

            # Small wait for initial render
            time.sleep(4)

            # NAME
            for sel in SELECTORS['name']:
                name = _safe_find_text(self.driver, sel, By.CSS_SELECTOR, timeout=4)
                if name:
                    result['name'] = name
                    print(f"   ✓ Name: {name}")
                    break
            if not result['name']:
                # fallback to title
                title = self.driver.title or ""
                if ' - Google Maps' in title:
                    result['name'] = title.replace(' - Google Maps', '').strip()
                    print(f"   ✓ Name (from title): {result['name']}")

            # RATING
            for sel in SELECTORS['rating']:
                rating_text = _safe_find_text(self.driver, sel, By.CSS_SELECTOR, timeout=3)
                if rating_text and re.match(r'^\d+(\.\d+)?$', rating_text.strip()):
                    result['rating'] = float(rating_text.replace(',', '.'))
                    print(f"   ✓ Rating: {result['rating']}")
                    break

            # TOTAL REVIEWS (aria-label on review button)
            for sel in SELECTORS['review_count_buttons']:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    aria = _attr_or_none(el, 'aria-label')
                    parsed = _parse_int_from_aria(aria)
                    if parsed:
                        result['total_reviews'] = parsed
                        print(f"   ✓ Total reviews: {parsed}")
                        break
                except:
                    continue

            # ADDRESS
            try:
                addr_el = self.driver.find_element(By.CSS_SELECTOR, SELECTORS['address_button'])
                aria = _attr_or_none(addr_el, 'aria-label') or ''
                if aria:
                    result['address'] = re.sub(r'Address:\s*', '', aria, flags=re.IGNORECASE).strip()
                    print("   ✓ Address found")
            except:
                pass

            # PHONE
            for sel in SELECTORS['phone_buttons']:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    aria = _attr_or_none(el, 'aria-label') or ''
                    if aria:
                        phone = aria.replace('Phone:', '').replace('Copy phone number', '').strip()
                        if phone:
                            result['phone'] = phone
                            print("   ✓ Phone found")
                            break
                except:
                    continue

            # WEBSITE
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, SELECTORS['website_link'])
                href = _attr_or_none(el, 'href')
                if href:
                    result['website'] = href
                    print("   ✓ Website found")
            except:
                pass

            # REVIEWS: click reviews tab if present
            print("→ Attempting to open Reviews")
            clicked = False
            for by, sel in SELECTORS['reviews_tab_buttons']:
                try:
                    btn = _safe_find_element(self.driver, by, sel, timeout=6)
                    if btn:
                        aria = _attr_or_none(btn, 'aria-label') or ''
                        parsed = _parse_int_from_aria(aria)
                        if parsed and result['total_reviews'] == 0:
                            result['total_reviews'] = parsed
                        self.driver.execute_script("arguments[0].click();", btn)
                        clicked = True
                        time.sleep(2)
                        print("   ✓ Reviews tab clicked")
                        break
                except:
                    continue

            if not clicked:
                print("   i) Reviews tab not clickable / not found — continuing with what we have")

            # Try to sort by Lowest rating (best-effort)
            print("→ Trying to sort reviews by lowest")
            for by, sel in SELECTORS['sort_buttons']:
                btn = _safe_find_element(self.driver, by, sel, timeout=4)
                if btn:
                    try:
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                        # click lowest option
                        for by2, sel2 in SELECTORS['lowest_option']:
                            low = _safe_find_element(self.driver, by2, sel2, timeout=3)
                            if low:
                                self.driver.execute_script("arguments[0].click();", low)
                                time.sleep(2)
                                print("   ✓ Sorted by lowest")
                                break
                        break
                    except:
                        continue

            # Extract negative reviews
            print("→ Extracting negative reviews")
            negatives = self._extract_negative_reviews()
            result['recent_negative_reviews'] = negatives

            # Find first review quick
            print("→ Determining first review date (fast method)")
            first_date = self._find_first_review_fast()
            result['first_review_date'] = first_date

            # If total_reviews still zero but we saw negatives, set approximate
            if result['total_reviews'] == 0 and negatives:
                result['total_reviews'] = len(negatives)

            return result

        except Exception as e:
            return {"error": f"Extraction failed: {repr(e)}"}

        finally:
            self._close()

    def _extract_negative_reviews(self) -> List[Dict]:
        driver = self.driver
        negatives = []
        seen = set()

        # Find a scrollable container to load more reviews (best-effort)
        scrollable = None
        for sel in SELECTORS['scrollable']:
            try:
                scrollable = driver.find_element(By.CSS_SELECTOR, sel)
                if scrollable:
                    break
            except:
                continue

        if scrollable:
            for _ in range(SCROLL_ATTEMPTS):
                try:
                    driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
                    time.sleep(1.2)
                except:
                    break

        # Collect review elements (choose selector with most hits)
        review_elements = []
        for sel in SELECTORS['review_containers']:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if len(elems) > len(review_elements):
                    review_elements = elems
            except:
                continue

        # Limit how many we process (safety)
        for el in review_elements[:30]:
            try:
                # rating: look for aria-label on star icon
                rating = None
                try:
                    stars = el.find_elements(By.CSS_SELECTOR, SELECTORS['rating_icon'])
                    for s in stars:
                        aria = _attr_or_none(s, 'aria-label') or ''
                        m = re.search(r'(\d+)\s*star', aria, re.IGNORECASE)
                        if m:
                            rating = int(m.group(1))
                            break
                except:
                    rating = None

                if rating is None:
                    rating = 1  # fallback conservative

                # We only want negative reviews (<=2)
                if rating > 2:
                    continue

                # Expand "more" if present
                try:
                    for bsel in SELECTORS['expand_buttons']:
                        btns = el.find_elements(By.CSS_SELECTOR, bsel)
                        for b in btns:
                            try:
                                if b.is_displayed():
                                    driver.execute_script("arguments[0].click();", b)
                                    time.sleep(0.2)
                                    break
                            except:
                                continue
                except:
                    pass

                # Extract text
                text = None
                for tsel in SELECTORS['review_text']:
                    try:
                        t = el.find_element(By.CSS_SELECTOR, tsel).text.strip()
                        if t:
                            text = t
                            break
                    except:
                        continue

                # Extract date text (human readable like '3 years ago')
                date_text = None
                for dsel in SELECTORS['review_date']:
                    try:
                        d = el.find_element(By.CSS_SELECTOR, dsel).text.strip()
                        if d:
                            date_text = d
                            break
                    except:
                        continue

                if not text or len(text) < 15:
                    continue

                # dedupe
                h = (text[:80], rating)
                if h in seen:
                    continue
                seen.add(h)

                negatives.append({
                    "text": text,
                    "rating": rating,
                    "date": date_text or "Recent"
                })
                print(f"   ✓ Negative review #{len(negatives)} (rating={rating})")
                if len(negatives) >= NEGATIVE_REVIEW_LIMIT:
                    break

            except Exception:
                continue

        print(f"   → Extracted {len(negatives)} negative reviews")
        return negatives

    def _find_first_review_fast(self) -> Optional[str]:
        """
        Attempt multiple fast methods:
         1) JSON-LD metadata (datePublished)
         2) regex searching in page_source for 'X years/months/weeks ago'
         3) visible date elements
         Fallback: "Several years ago"
        """
        driver = self.driver

        # 1) JSON-LD
        try:
            src = driver.page_source
            json_ld_matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', src, re.DOTALL | re.IGNORECASE)
            for raw in json_ld_matches:
                try:
                    data = json.loads(raw.strip())
                    if isinstance(data, dict) and 'review' in data:
                        reviews = data['review'] if isinstance(data['review'], list) else [data['review']]
                        dates = []
                        for r in reviews:
                            dp = r.get('datePublished') if isinstance(r, dict) else None
                            if dp:
                                dates.append(dp)
                        if dates:
                            oldest = min(dates)
                            try:
                                dt = datetime.fromisoformat(oldest.replace('Z', '+00:00'))
                                diff_days = (datetime.utcnow() - dt).days
                                years = diff_days // 365
                                months = (diff_days % 365) // 30
                                if years > 0:
                                    return f"{years} year{'s' if years>1 else ''} ago"
                                if months > 0:
                                    return f"{months} month{'s' if months>1 else ''} ago"
                                return "Recently"
                            except:
                                pass
                except:
                    continue
        except:
            pass

        # 2) regex on page source
        try:
            src = driver.page_source
            years = re.findall(r'(\d+)\s+years?\s+ago', src, re.IGNORECASE)
            months = re.findall(r'(\d+)\s+months?\s+ago', src, re.IGNORECASE)
            weeks = re.findall(r'(\d+)\s+weeks?\s+ago', src, re.IGNORECASE)

            if years:
                maxy = max(int(x) for x in years)
                return f"{maxy} year{'s' if maxy>1 else ''} ago"
            if months:
                m = max(int(x) for x in months)
                return f"{m} month{'s' if m>1 else ''} ago"
            if weeks:
                w = max(int(x) for x in weeks)
                return f"{w} week{'s' if w>1 else ''} ago"
        except:
            pass

        # 3) visible date elements
        try:
            date_elems = driver.find_elements(By.CSS_SELECTOR, SELECTORS['review_date'][0])
            visible = [e.text.strip() for e in date_elems if e.text.strip()]
            if visible:
                # prefer the biggest "X years" found
                best = None
                max_y = 0
                for v in visible:
                    y = _parse_date_ago_text(v)
                    if y and y > max_y:
                        max_y = y
                        best = v
                if max_y > 0:
                    return best
        except:
            pass

        # fallback
        return "Several years ago"


# ---------- Example usage ----------
# ---------- Example usage ----------
if __name__ == "__main__":
    print("\nEnter Google Maps Place URL:")
    TEST_URL = input("URL: ").strip()

    if not TEST_URL:
        print("❌ No URL entered. Exiting.")
        exit()

    extractor = GoogleMapsExtractorA(headless=True)

    # Extract all details, but show only key metrics
    data = extractor.get_place_details(TEST_URL)

    # ---- PRINT ONLY KEY METRICS ----
    print("\n========== KEY METRICS ==========")
    print(f"Name:              {data.get('name')}")
    print(f"Rating:            {data.get('rating')}")
    print(f"Total Reviews:     {data.get('total_reviews')}")
    print(f"First Review Date: {data.get('first_review_date')}")
    print("=================================\n")

    # If you want to debug full output, uncomment below:
    # print(json.dumps(data, indent=2, ensure_ascii=False))


