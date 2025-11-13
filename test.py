import re
import json
import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import warnings

# Suppress ALL warnings and errors
warnings.filterwarnings('ignore')
os.environ['WDM_LOG'] = '0'
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Redirect stderr to suppress Chrome errors
if os.name == 'nt':
    sys.stderr = open('NUL', 'w')
else:
    sys.stderr = open('/dev/null', 'w')

class GoogleMapsExtractor:
    def __init__(self):
        self.driver = None
    
    def _setup_driver(self):
        """Setup Chrome driver with all errors suppressed"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-dev-tools')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--silent')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        service = Service(
            ChromeDriverManager().install(),
            log_path='NUL' if os.name == 'nt' else '/dev/null',
            service_args=['--silent']
        )
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        
    def _close_driver(self):
        """Close the driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def get_place_details(self, url: str) -> Dict:
        """Extract business details from Google Maps URL"""
        try:
            print("🌐 Starting browser...")
            self._setup_driver()
            
            print("📍 Loading Google Maps page...")
            self.driver.get(url)
            time.sleep(8)
            
            business_info = {
                'name': None,
                'address': None,
                'rating': None,
                'total_reviews': 0,
                'phone': None,
                'website': None,
                'first_review_date': None,
                'recent_negative_reviews': []
            }
            
            print("🔍 Extracting business information from Overview...")
            
            # Extract name
            try:
                name_selectors = ['h1.DUwDvf', 'h1.fontHeadlineLarge', 'h1']
                for selector in name_selectors:
                    try:
                        name_element = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if name_element and name_element.text.strip():
                            business_info['name'] = name_element.text.strip()
                            print(f"   ✓ Name: {business_info['name']}")
                            break
                    except:
                        continue
                
                if not business_info['name']:
                    title = self.driver.title
                    if title and ' - Google Maps' in title:
                        business_info['name'] = title.replace(' - Google Maps', '').strip()
                        print(f"   ✓ Name: {business_info['name']}")
            except:
                pass
            
            # Extract rating
            try:
                time.sleep(2)
                rating_selectors = [
                    'div.F7nice span[aria-hidden="true"]',
                    'span.ceNzKf[aria-hidden="true"]',
                ]
                
                for selector in rating_selectors:
                    try:
                        rating_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        rating_text = rating_element.text.strip()
                        if rating_text and re.match(r'^\d\.?\d?$', rating_text):
                            business_info['rating'] = float(rating_text.replace(',', '.'))
                            print(f"   ✓ Rating: {business_info['rating']}")
                            break
                    except:
                        continue
            except:
                pass
            
            # Extract total reviews - IMPROVED AND FIXED
            try:
                time.sleep(1)
                
                # Method 1: From aria-label of button
                review_count_selectors = [
                    'div.F7nice button[aria-label*="reviews"]',
                    'button[aria-label*="reviews"]',
                    'div.F7nice button[aria-label*="review"]',
                ]
                
                for selector in review_count_selectors:
                    try:
                        review_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        aria_label = review_element.get_attribute('aria-label')
                        
                        if aria_label and 'review' in aria_label.lower():
                            match = re.search(r'([\d,]+)\s*review', aria_label, re.IGNORECASE)
                            if match:
                                business_info['total_reviews'] = int(match.group(1).replace(',', ''))
                                print(f"   ✓ Total Reviews: {business_info['total_reviews']}")
                                break
                    except:
                        continue
                
                # Method 2: From visible text next to rating
                if business_info['total_reviews'] == 0:
                    try:
                        rating_section = self.driver.find_element(By.CSS_SELECTOR, 'div.F7nice')
                        all_text = rating_section.text
                        
                        # Pattern: (1,234)
                        match = re.search(r'\(([\d,]+)\)', all_text)
                        if match:
                            business_info['total_reviews'] = int(match.group(1).replace(',', ''))
                            print(f"   ✓ Total Reviews: {business_info['total_reviews']}")
                    except:
                        pass
                
                # Method 3: From span elements containing review count
                if business_info['total_reviews'] == 0:
                    try:
                        rating_area = self.driver.find_element(By.CSS_SELECTOR, 'div.F7nice')
                        all_spans = rating_area.find_elements(By.TAG_NAME, 'span')
                        
                        for span in all_spans:
                            span_text = span.text.strip()
                            if '(' in span_text and ')' in span_text:
                                match = re.search(r'\(([\d,]+)\)', span_text)
                                if match:
                                    business_info['total_reviews'] = int(match.group(1).replace(',', ''))
                                    print(f"   ✓ Total Reviews: {business_info['total_reviews']}")
                                    break
                            elif 'review' in span_text.lower():
                                match = re.search(r'([\d,]+)', span_text)
                                if match:
                                    business_info['total_reviews'] = int(match.group(1).replace(',', ''))
                                    print(f"   ✓ Total Reviews: {business_info['total_reviews']}")
                                    break
                    except:
                        pass
                
                # Method 4: From buttons without aria-label
                if business_info['total_reviews'] == 0:
                    try:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, 'div.F7nice button')
                        for button in buttons:
                            button_text = button.text.strip()
                            if button_text and any(char.isdigit() for char in button_text):
                                match = re.search(r'([\d,]+)', button_text)
                                if match:
                                    potential_count = int(match.group(1).replace(',', ''))
                                    if 1 <= potential_count <= 1000000:
                                        business_info['total_reviews'] = potential_count
                                        print(f"   ✓ Total Reviews: {business_info['total_reviews']}")
                                        break
                    except:
                        pass
                
                # Method 5: Parse from page source
                if business_info['total_reviews'] == 0:
                    try:
                        page_source = self.driver.page_source
                        patterns = [
                            r'"userReviewCount":(\d+)',
                            r'"reviewCount":(\d+)',
                            r'(\d{1,3}(?:,\d{3})*)\s*reviews?',
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, page_source, re.IGNORECASE)
                            if matches:
                                for match in matches:
                                    try:
                                        count = int(match.replace(',', ''))
                                        if 1 <= count <= 1000000:
                                            business_info['total_reviews'] = count
                                            print(f"   ✓ Total Reviews: {business_info['total_reviews']}")
                                            break
                                    except:
                                        continue
                                if business_info['total_reviews'] > 0:
                                    break
                    except:
                        pass
                
            except:
                pass
            
            # Extract address
            try:
                address_button = self.driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="address"]')
                aria_label = address_button.get_attribute('aria-label')
                if aria_label:
                    business_info['address'] = aria_label.replace('Address: ', '').strip()
                    print(f"   ✓ Address found")
            except:
                pass
            
            # Extract phone
            try:
                phone_selectors = ['button[data-item-id*="phone"]', 'button[aria-label*="Phone"]']
                for selector in phone_selectors:
                    try:
                        phone_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        aria_label = phone_button.get_attribute('aria-label')
                        if aria_label:
                            business_info['phone'] = aria_label.replace('Phone: ', '').replace('Copy phone number', '').strip()
                            print(f"   ✓ Phone found")
                            break
                    except:
                        continue
            except:
                pass
            
            # Extract website
            try:
                website_link = self.driver.find_element(By.CSS_SELECTOR, 'a[data-item-id="authority"]')
                business_info['website'] = website_link.get_attribute('href')
                print(f"   ✓ Website found")
            except:
                pass
            
            # Extract reviews
            print("\n💬 Loading reviews section...")
            reviews_data = self._extract_reviews_with_sorting()
            business_info['recent_negative_reviews'] = reviews_data.get('negative_reviews', [])
            business_info['first_review_date'] = reviews_data.get('first_review_date')
            
            if business_info['total_reviews'] == 0 and reviews_data.get('total_count'):
                business_info['total_reviews'] = reviews_data['total_count']
            
            return business_info
            
        except Exception as e:
            return {'error': f'Extraction failed: {str(e)}'}
        finally:
            self._close_driver()
    
    def _extract_reviews_with_sorting(self) -> Dict:
        """Extract reviews with sorting"""
        reviews_data = {
            'negative_reviews': [],
            'first_review_date': None,
            'total_count': 0
        }
        
        try:
            # Click Reviews tab
            print("   Clicking on Reviews tab...")
            reviews_buttons = [
                (By.XPATH, '//button[contains(@aria-label, "Reviews")]'),
                (By.XPATH, '//button[contains(@aria-label, "reviews")]'),
                (By.CSS_SELECTOR, 'button[aria-label*="review"]'),
            ]
            
            clicked = False
            for by, selector in reviews_buttons:
                try:
                    reviews_button = self.wait.until(EC.element_to_be_clickable((by, selector)))
                    aria_label = reviews_button.get_attribute('aria-label')
                    if aria_label:
                        match = re.search(r'([\d,]+)\s*review', aria_label, re.IGNORECASE)
                        if match:
                            reviews_data['total_count'] = int(match.group(1).replace(',', ''))
                    
                    self.driver.execute_script("arguments[0].click();", reviews_button)
                    print("   Reviews tab clicked!")
                    time.sleep(3)
                    clicked = True
                    break
                except:
                    continue
            
            if not clicked:
                return reviews_data
            
            # Sort by lowest rating
            print("   Looking for Sort button...")
            try:
                sort_buttons = [
                    (By.XPATH, '//button[contains(@aria-label, "Sort reviews")]'),
                    (By.XPATH, '//button[@data-value="Sort"]'),
                    (By.CSS_SELECTOR, 'button[aria-label*="Sort"]'),
                ]
                
                for by, selector in sort_buttons:
                    try:
                        sort_button = self.wait.until(EC.element_to_be_clickable((by, selector)))
                        self.driver.execute_script("arguments[0].click();", sort_button)
                        print("   Sort button clicked!")
                        time.sleep(2)
                        
                        # Select lowest rating
                        print("   Selecting 'Lowest rating' option...")
                        lowest_options = [
                            (By.XPATH, '//div[@role="menuitemradio" and contains(., "Lowest")]'),
                            (By.XPATH, '//div[@role="menuitemradio" and contains(., "lowest")]'),
                        ]
                        
                        for by2, selector2 in lowest_options:
                            try:
                                lowest_option = self.wait.until(EC.element_to_be_clickable((by2, selector2)))
                                self.driver.execute_script("arguments[0].click();", lowest_option)
                                print("   ✓ Sorted by lowest rating!")
                                time.sleep(3)
                                break
                            except:
                                continue
                        break
                    except:
                        continue
            except:
                pass
            
            # Extract negative reviews
            print("   Extracting negative reviews...")
            negative_reviews = self._extract_negative_reviews()
            reviews_data['negative_reviews'] = negative_reviews
            
            # Find first review
            print("   Finding first review date...")
            first_review_date = self._find_first_review_fast()
            reviews_data['first_review_date'] = first_review_date
            
        except:
            pass
        
        return reviews_data
    
    def _extract_negative_reviews(self) -> List[Dict]:
        """Extract negative reviews with full text"""
        negative_reviews = []
        
        try:
            # Scroll to load reviews
            print("   Scrolling to load reviews...")
            scrollable_selectors = [
                'div.m6QErb.DxyBCb.kA9KIf.dS8AEf',
                'div[role="main"]',
                'div.m6QErb',
            ]
            
            scrollable_div = None
            for selector in scrollable_selectors:
                try:
                    scrollable_div = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if scrollable_div:
                        break
                except:
                    continue
            
            if scrollable_div:
                for i in range(3):
                    self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                    time.sleep(1.5)
            
            # Find reviews
            review_elements = []
            selectors = ['div.jftiEf', 'div.WMbnJf', 'div[data-review-id]']
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(elements) > len(review_elements):
                        review_elements = elements
                except:
                    continue
            
            print(f"   Found {len(review_elements)} review elements")
            
            seen_reviews = set()
            
            for review_element in review_elements[:15]:
                try:
                    # Get rating
                    rating = None
                    try:
                        rating_spans = review_element.find_elements(By.CSS_SELECTOR, 'span[role="img"][aria-label]')
                        for span in rating_spans:
                            aria_label = span.get_attribute('aria-label')
                            if aria_label and 'star' in aria_label.lower():
                                match = re.search(r'(\d+)\s*star', aria_label, re.IGNORECASE)
                                if match:
                                    rating = int(match.group(1))
                                    break
                        
                        if not rating:
                            rating = 1
                    except:
                        rating = 1
                    
                    if rating and rating > 2:
                        continue
                    
                    # Get text - Click "More" button first
                    text = None
                    try:
                        # Try to expand review first
                        try:
                            more_buttons = review_element.find_elements(By.CSS_SELECTOR, 'button.w8nwRe')
                            for more_button in more_buttons:
                                try:
                                    if more_button.is_displayed():
                                        self.driver.execute_script("arguments[0].click();", more_button)
                                        time.sleep(0.3)
                                        break
                                except:
                                    continue
                        except:
                            pass
                        
                        # Now get the full text
                        text_selectors = ['span.wiI7pd', 'span.MyEned', 'div.MyEned']
                        
                        for selector in text_selectors:
                            try:
                                text_element = review_element.find_element(By.CSS_SELECTOR, selector)
                                if text_element and text_element.text.strip():
                                    text = text_element.text.strip()
                                    break
                            except:
                                continue
                    except:
                        pass
                    
                    # Get date
                    date = None
                    date_selectors = ['span.rsqaWe', 'span.DU9Pgb']
                    for selector in date_selectors:
                        try:
                            date_element = review_element.find_element(By.CSS_SELECTOR, selector)
                            if date_element and date_element.text.strip():
                                date = date_element.text.strip()
                                break
                        except:
                            continue
                    
                    # Add review
                    if text and len(text) > 15:
                        review_hash = f"{text[:50]}_{rating}"
                        if review_hash not in seen_reviews:
                            seen_reviews.add(review_hash)
                            negative_reviews.append({
                                'text': text,
                                'rating': rating if rating else 'N/A',
                                'date': date if date else 'Recent'
                            })
                            print(f"   ✓ Negative review #{len(negative_reviews)} (Rating: {rating})")
                            
                            if len(negative_reviews) >= 10:
                                break
                except:
                    continue
            
            print(f"   Total negative reviews extracted: {len(negative_reviews)}")
            
        except:
            pass
        
        return negative_reviews
    
    def _find_first_review_fast(self) -> Optional[str]:
        """Fast method to find first review without scrolling"""
        try:
            # Method 1: Check JSON-LD metadata
            print("   Checking structured data...")
            try:
                page_source = self.driver.page_source
                json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
                json_matches = re.findall(json_ld_pattern, page_source, re.DOTALL)
                
                for json_str in json_matches:
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, dict) and 'review' in data:
                            reviews = data['review'] if isinstance(data['review'], list) else [data['review']]
                            dates = []
                            for review in reviews:
                                if 'datePublished' in review:
                                    dates.append(review['datePublished'])
                            
                            if dates:
                                oldest = min(dates)
                                try:
                                    date_obj = datetime.fromisoformat(oldest.replace('Z', '+00:00'))
                                    years_ago = (datetime.now() - date_obj).days // 365
                                    months_ago = ((datetime.now() - date_obj).days % 365) // 30
                                    
                                    if years_ago > 0:
                                        oldest_text = f"{years_ago} year{'s' if years_ago > 1 else ''} ago"
                                    elif months_ago > 0:
                                        oldest_text = f"{months_ago} month{'s' if months_ago > 1 else ''} ago"
                                    else:
                                        oldest_text = "Recently"
                                    
                                    print(f"   ✓ First review from metadata: {oldest_text}")
                                    return oldest_text
                                except:
                                    pass
                    except:
                        continue
            except:
                pass
            
            # Method 2: Parse page source for all dates
            print("   Analyzing page data...")
            try:
                page_source = self.driver.page_source
                
                all_years = re.findall(r'(\d+)\s+years?\s+ago', page_source, re.IGNORECASE)
                all_months = re.findall(r'(\d+)\s+months?\s+ago', page_source, re.IGNORECASE)
                all_weeks = re.findall(r'(\d+)\s+weeks?\s+ago', page_source, re.IGNORECASE)
                
                years = [int(y) for y in all_years] if all_years else []
                months = [int(m) for m in all_months] if all_months else []
                weeks = [int(w) for w in all_weeks] if all_weeks else []
                
                if years:
                    max_years = max(years)
                    oldest_text = f"{max_years} year{'s' if max_years > 1 else ''} ago"
                    print(f"   ✓ First review found: {oldest_text}")
                    return oldest_text
                elif months:
                    max_months = max(months)
                    oldest_text = f"{max_months} month{'s' if max_months > 1 else ''} ago"
                    print(f"   ✓ First review found: {oldest_text}")
                    return oldest_text
                elif weeks:
                    max_weeks = max(weeks)
                    oldest_text = f"{max_weeks} week{'s' if max_weeks > 1 else ''} ago"
                    print(f"   ✓ First review found: {oldest_text}")
                    return oldest_text
            except:
                pass
            
            # Method 3: Check visible dates
            print("   Checking visible reviews...")
            try:
                time.sleep(1)
                date_elements = self.driver.find_elements(By.CSS_SELECTOR, 'span.rsqaWe')
                visible_dates = [elem.text.strip() for elem in date_elements if elem.text.strip()]
                
                if visible_dates:
                    max_years = 0
                    best_date = visible_dates[0]
                    
                    for date in visible_dates:
                        match = re.search(r'(\d+)\s+year', date, re.IGNORECASE)
                        if match:
                            years = int(match.group(1))
                            if years > max_years:
                                max_years = years
                                best_date = date
                    
                    if max_years > 0:
                        print(f"   ✓ First review found: {best_date}")
                        return best_date
            except:
                pass
            
            # Fallback
            print("   Using estimation...")
            return "Several years ago"
            
        except:
            return None