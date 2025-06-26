import requests
import pandas as pd
import json
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from geopy.geocoders import Nominatim
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('free_spice_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class BusinessData:
    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    cuisine_type: Optional[str] = None
    price_level: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    business_type: str = "restaurant"
    postcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: str = "unknown"

class FreeSpiceExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.results = []
        self.geolocator = Nominatim(user_agent="spice_business_extractor_2025")
        
    def get_hackney_postcodes(self) -> List[str]:
        """Get Hackney postcodes for targeting"""
        hackney_postcodes = [
            "E5 0", "E5 8", "E5 9", "E8 1", "E8 2", "E8 3", "E8 4", 
            "E9 5", "E9 6", "E9 7", "N1 4", "N1 5", "N1 6", "N16 0", 
            "N16 5", "N16 6", "N16 7", "N16 8", "N16 9"
        ]
        logger.info(f"Targeting {len(hackney_postcodes)} Hackney postcodes")
        return hackney_postcodes
    
    def extract_overpass_api_businesses(self, postcode: str) -> List[BusinessData]:
        """Extract businesses using free Overpass API (OpenStreetMap data)"""
        businesses = []
        
        try:
            # Get coordinates for postcode
            location = self.geolocator.geocode(f"{postcode}, London, UK")
            if not location:
                logger.warning(f"Could not geocode {postcode}")
                return businesses
            
            lat, lng = location.latitude, location.longitude
            
            # Overpass API query for restaurants and food businesses
            overpass_query = f"""
            [out:json][timeout:25];
            (
              nwr["amenity"~"^(restaurant|fast_food|cafe|bar|pub)$"](around:1000,{lat},{lng});
              nwr["cuisine"~"indian|asian|chinese|thai|middle_eastern|curry"](around:1000,{lat},{lng});
              nwr["shop"="spices"](around:1000,{lat},{lng});
            );
            out center meta;
            """
            
            overpass_url = "http://overpass-api.de/api/interpreter"
            
            response = self.session.post(overpass_url, data=overpass_query, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                businesses.extend(self._parse_overpass_data(data, postcode))
                logger.info(f"Overpass API: Found {len(businesses)} businesses near {postcode}")
            else:
                logger.warning(f"Overpass API failed for {postcode}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Overpass API error for {postcode}: {str(e)}")
            
        return businesses
    
    def _parse_overpass_data(self, data: Dict, postcode: str) -> List[BusinessData]:
        """Parse Overpass API response data"""
        businesses = []
        
        try:
            for element in data.get('elements', []):
                tags = element.get('tags', {})
                
                name = tags.get('name', 'Unknown Business')
                amenity = tags.get('amenity', '')
                cuisine = tags.get('cuisine', '')
                
                # Skip if no useful name
                if name == 'Unknown Business' and not cuisine:
                    continue
                
                # Get coordinates
                if element['type'] == 'node':
                    lat, lng = element.get('lat'), element.get('lon')
                elif 'center' in element:
                    lat, lng = element['center']['lat'], element['center']['lon']
                else:
                    lat, lng = None, None
                
                # Build address from tags
                address_parts = []
                for addr_key in ['addr:housenumber', 'addr:street', 'addr:city', 'addr:postcode']:
                    if addr_key in tags:
                        address_parts.append(tags[addr_key])
                
                address = ', '.join(address_parts) if address_parts else f"Near {postcode}, London"
                
                business = BusinessData(
                    name=name,
                    address=address,
                    phone=tags.get('phone'),
                    website=tags.get('website'),
                    cuisine_type=cuisine or amenity,
                    latitude=lat,
                    longitude=lng,
                    postcode=postcode,
                    source="OpenStreetMap"
                )
                
                businesses.append(business)
                
        except Exception as e:
            logger.error(f"Error parsing Overpass data: {str(e)}")
            
        return businesses
    
    def extract_yelp_public_data(self, postcode: str) -> List[BusinessData]:
        """Extract public Yelp data for restaurants (no API key needed)"""
        businesses = []
        
        try:
            # Target spice-heavy cuisines
            cuisines = ['indian', 'asian', 'chinese', 'thai', 'middle-eastern']
            
            for cuisine in cuisines:
                search_url = f"https://www.yelp.com/search"
                params = {
                    'find_desc': f'{cuisine} restaurants',
                    'find_loc': f'{postcode}, London, UK',
                    'start': 0
                }
                
                response = self.session.get(search_url, params=params, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    businesses.extend(self._parse_yelp_results(soup, postcode, cuisine))
                    time.sleep(2)  # Rate limiting
                else:
                    logger.warning(f"Yelp request failed for {cuisine} in {postcode}")
                    
        except Exception as e:
            logger.error(f"Yelp extraction error for {postcode}: {str(e)}")
            
        return businesses
    
    def _parse_yelp_results(self, soup: BeautifulSoup, postcode: str, cuisine: str) -> List[BusinessData]:
        """Parse Yelp search results"""
        businesses = []
        
        try:
            # Look for business containers (Yelp structure may change)
            business_containers = soup.find_all('div', {'data-testid': 'serp-ia-card'}) or \
                                 soup.find_all('div', class_=re.compile(r'searchResult'))
            
            for container in business_containers[:5]:  # Limit to first 5 results
                try:
                    # Extract business name
                    name_elem = container.find('a', class_=re.compile(r'businessname')) or \
                               container.find('h3') or \
                               container.find('h4')
                    
                    name = name_elem.get_text(strip=True) if name_elem else "Unknown Restaurant"
                    
                    # Extract address
                    address_elem = container.find('span', class_=re.compile(r'address')) or \
                                  container.find('p', class_=re.compile(r'address'))
                    
                    address = address_elem.get_text(strip=True) if address_elem else f"Near {postcode}, London"
                    
                    # Extract rating
                    rating_elem = container.find('span', class_=re.compile(r'rating'))
                    rating = None
                    if rating_elem:
                        rating_text = rating_elem.get_text(strip=True)
                        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))
                    
                    business = BusinessData(
                        name=name,
                        address=address,
                        cuisine_type=cuisine,
                        rating=rating,
                        postcode=postcode,
                        source="Yelp Public"
                    )
                    
                    businesses.append(business)
                    
                except Exception as e:
                    logger.warning(f"Error parsing individual Yelp result: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing Yelp results: {str(e)}")
            
        return businesses
    
    def extract_google_my_business_free(self, postcode: str) -> List[BusinessData]:
        """Extract Google My Business data using free methods"""
        businesses = []
        
        try:
            # Set up Chrome driver for dynamic content
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            # Search for spice-heavy restaurants
            search_terms = ['indian restaurants', 'asian restaurants', 'curry houses']
            
            for term in search_terms:
                try:
                    search_url = f"https://www.google.com/maps/search/{term}+near+{postcode.replace(' ', '+')}+London"
                    driver.get(search_url)
                    
                    # Wait for results to load
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="article"]'))
                    )
                    
                    time.sleep(3)  # Additional wait for dynamic content
                    
                    # Extract business information
                    business_elements = driver.find_elements(By.CSS_SELECTOR, '[role="article"]')
                    
                    for elem in business_elements[:3]:  # Limit to first 3 per search
                        try:
                            name = elem.find_element(By.CSS_SELECTOR, '[data-value="Name"]').text
                            address = elem.find_element(By.CSS_SELECTOR, '[data-value="Address"]').text
                            
                            # Try to get rating
                            rating = None
                            try:
                                rating_elem = elem.find_element(By.CSS_SELECTOR, '[data-value="Rating"]')
                                rating = float(rating_elem.text)
                            except:
                                pass
                            
                            business = BusinessData(
                                name=name,
                                address=address,
                                cuisine_type=term,
                                rating=rating,
                                postcode=postcode,
                                source="Google Maps"
                            )
                            
                            businesses.append(business)
                            
                        except Exception as e:
                            logger.warning(f"Error extracting Google Maps business: {str(e)}")
                            continue
                    
                    time.sleep(2)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Google Maps search error for {term}: {str(e)}")
                    continue
            
            driver.quit()
            
        except Exception as e:
            logger.error(f"Google My Business extraction error for {postcode}: {str(e)}")
            
        return businesses
    
    def enhance_business_data(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Enhance business data with additional information"""
        enhanced = []
        
        for business in businesses:
            try:
                # Generate email if website exists
                if business.website and not business.email:
                    domain = business.website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
                    business.email = f"info@{domain}"
                
                # Get coordinates if missing
                if not business.latitude and business.address:
                    location = self.geolocator.geocode(business.address)
                    if location:
                        business.latitude = location.latitude
                        business.longitude = location.longitude
                
                enhanced.append(business)
                
            except Exception as e:
                logger.error(f"Error enhancing {business.name}: {str(e)}")
                enhanced.append(business)
                
        return enhanced
    
    def prioritize_spice_businesses(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Prioritize businesses likely to use spices heavily"""
        spice_keywords = [
            'indian', 'curry', 'asian', 'chinese', 'thai', 'middle eastern',
            'bengali', 'pakistani', 'tandoori', 'spice', 'oriental', 'kitchen'
        ]
        
        high_priority = []
        medium_priority = []
        low_priority = []
        
        for business in businesses:
            score = 0
            
            # Check name for spice-related keywords
            name_lower = business.name.lower()
            for keyword in spice_keywords:
                if keyword in name_lower:
                    score += 2
            
            # Check cuisine type
            if business.cuisine_type:
                cuisine_lower = business.cuisine_type.lower()
                for keyword in spice_keywords:
                    if keyword in cuisine_lower:
                        score += 3
            
            # Categorize by priority
            if score >= 4:
                high_priority.append(business)
            elif score >= 2:
                medium_priority.append(business)
            else:
                low_priority.append(business)
        
        logger.info(f"Prioritized: {len(high_priority)} high, {len(medium_priority)} medium, {len(low_priority)} low priority")
        
        return high_priority + medium_priority + low_priority
    
    def save_results(self, businesses: List[BusinessData], filename: str = "spice_leads_free.csv"):
        """Save results to CSV and JSON"""
        try:
            data = []
            for business in businesses:
                data.append({
                    'Business Name': business.name,
                    'Address': business.address,
                    'Postcode': business.postcode,
                    'Phone': business.phone,
                    'Website': business.website,
                    'Email': business.email,
                    'Cuisine Type': business.cuisine_type,
                    'Price Level': business.price_level,
                    'Rating': business.rating,
                    'Reviews Count': business.reviews_count,
                    'Latitude': business.latitude,
                    'Longitude': business.longitude,
                    'Source': business.source
                })
            
            # Save CSV
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            logger.info(f"Saved {len(data)} businesses to {filename}")
            
            # Save JSON
            json_filename = filename.replace('.csv', '.json')
            with open(json_filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            return filename
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            return None
    
    def run_extraction(self):
        """Main extraction process using free APIs"""
        logger.info("🚀 Starting FREE spice business extraction for Hackney")
        
        all_businesses = []
        postcodes = self.get_hackney_postcodes()
        
        for i, postcode in enumerate(postcodes[:5], 1):  # Test with first 5 postcodes
            logger.info(f"📍 Processing {postcode} ({i}/{min(5, len(postcodes))})")
            
            try:
                # Method 1: OpenStreetMap/Overpass API (Free)
                osm_businesses = self.extract_overpass_api_businesses(postcode)
                all_businesses.extend(osm_businesses)
                logger.info(f"✅ OSM: {len(osm_businesses)} businesses")
                
                # Method 2: Yelp Public Data (Free scraping)
                yelp_businesses = self.extract_yelp_public_data(postcode)
                all_businesses.extend(yelp_businesses)
                logger.info(f"✅ Yelp: {len(yelp_businesses)} businesses")
                
                # Rate limiting between postcodes
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ Error processing {postcode}: {str(e)}")
                continue
        
        # Remove duplicates
        unique_businesses = self._remove_duplicates(all_businesses)
        logger.info(f"📊 Total unique businesses: {len(unique_businesses)}")
        
        # Prioritize spice users
        prioritized = self.prioritize_spice_businesses(unique_businesses)
        
        # Enhance data
        enhanced = self.enhance_business_data(prioritized)
        
        # Save results
        filename = self.save_results(enhanced)
        
        logger.info("✅ FREE extraction completed!")
        return enhanced, filename
    
    def _remove_duplicates(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Remove duplicate businesses"""
        seen = set()
        unique = []
        
        for business in businesses:
            key = f"{business.name.lower().strip()}_{business.address.lower().strip()}"
            if key not in seen:
                seen.add(key)
                unique.append(business)
        
        logger.info(f"🔄 Removed {len(businesses) - len(unique)} duplicates")
        return unique

if __name__ == "__main__":
    try:
        extractor = FreeSpiceExtractor()
        results, filename = extractor.run_extraction()
        
        print(f"\n🎉 FREE EXTRACTION COMPLETE!")
        print(f"📊 Total businesses: {len(results)}")
        print(f"💾 Saved to: {filename}")
        
        # Show top spice-focused results
        spice_businesses = [b for b in results if any(keyword in b.name.lower() or 
                                                    (b.cuisine_type and keyword in b.cuisine_type.lower())
                                                    for keyword in ['indian', 'curry', 'asian', 'spice'])]
        
        print(f"\n🌶️ TOP SPICE-FOCUSED BUSINESSES:")
        for i, business in enumerate(spice_businesses[:10], 1):
            print(f"{i}. {business.name} - {business.cuisine_type} ({business.source})")
        
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        print(f"❌ Error: {str(e)}") 