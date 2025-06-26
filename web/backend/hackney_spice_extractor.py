import requests
import pandas as pd
import json
import time
import logging
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
import re
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
os.makedirs('data', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/hackney_spice_extraction.log'),
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
    spice_priority: str = "low"  # high, medium, low

class HackneySpiceExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # API Keys (optional)
        self.google_api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        self.yelp_api_key = os.getenv('YELP_API_KEY')
        
        self.geolocator = Nominatim(user_agent="hackney_spice_extractor_2025")
        self.results = []
        
        logger.info(f"Google API Key: {'✅ Available' if self.google_api_key else '❌ Not set'}")
        logger.info(f"Yelp API Key: {'✅ Available' if self.yelp_api_key else '❌ Not set'}")
        
    def get_hackney_postcodes(self) -> List[str]:
        """Get actual Hackney postcodes based on London borough boundaries"""
        hackney_postcodes = [
            # E postcode areas in Hackney
            "E5",    # Clapton
            "E8",    # Hackney, Dalston
            "E9",    # Hackney Wick, South Hackney
            
            # N postcode areas in Hackney  
            "N1",    # Hoxton, De Beauvoir Town
            "N16",   # Stoke Newington, Stamford Hill
            
            # Specific areas
            "E2 8",  # Bethnal Green (partial)
            "E1 6",  # Whitechapel (partial)
            "N4 2",  # Finsbury Park (partial)
            "N7 6",  # Holloway (partial)
        ]
        
        # Expand to include specific district codes
        expanded_postcodes = []
        for base in hackney_postcodes:
            if len(base) == 2:  # E5, E8, etc.
                for i in range(10):
                    expanded_postcodes.append(f"{base} {i}")
            else:
                expanded_postcodes.append(base)
        
        logger.info(f"Targeting {len(expanded_postcodes)} Hackney postcodes")
        return expanded_postcodes
    
    def extract_overpass_businesses(self, postcode: str) -> List[BusinessData]:
        """Extract businesses using OpenStreetMap Overpass API"""
        businesses = []
        
        try:
            # Get coordinates for postcode area
            location = self.geolocator.geocode(f"{postcode}, Hackney, London, UK")
            if not location:
                # Try without specific district number
                base_postcode = postcode.split()[0]
                location = self.geolocator.geocode(f"{base_postcode}, Hackney, London, UK")
                
            if not location:
                logger.warning(f"Could not geocode {postcode}")
                return businesses
            
            lat, lng = location.latitude, location.longitude
            logger.info(f"Geocoded {postcode} to {lat:.4f}, {lng:.4f}")
            
            # Enhanced Overpass query targeting spice-heavy businesses
            overpass_query = f"""
            [out:json][timeout:30];
            (
              // Restaurants and food places
              nwr["amenity"~"^(restaurant|fast_food|cafe|bar|pub)$"](around:800,{lat},{lng});
              
              // Spice-focused cuisines
              nwr["cuisine"~"indian|asian|chinese|thai|middle_eastern|curry|bengali|pakistani|nepalese|sri_lankan"](around:800,{lat},{lng});
              
              // Food shops that might use spices
              nwr["shop"~"spices|convenience|supermarket|deli"](around:800,{lat},{lng});
              
              // Specific food types
              nwr["food"~"indian|chinese|thai|curry"](around:800,{lat},{lng});
            );
            out center meta;
            """
            
            overpass_url = "http://overpass-api.de/api/interpreter"
            
            response = self.session.post(overpass_url, data=overpass_query, timeout=45)
            
            if response.status_code == 200:
                data = response.json()
                businesses = self._parse_overpass_data(data, postcode)
                logger.info(f"OpenStreetMap: Found {len(businesses)} businesses near {postcode}")
            else:
                logger.warning(f"Overpass API failed for {postcode}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Overpass API error for {postcode}: {str(e)}")
            
        return businesses
    
    def _parse_overpass_data(self, data: Dict, postcode: str) -> List[BusinessData]:
        """Parse OpenStreetMap data with spice business prioritization"""
        businesses = []
        
        try:
            for element in data.get('elements', []):
                tags = element.get('tags', {})
                
                name = tags.get('name', '').strip()
                if not name or name.lower() in ['unknown', 'unnamed']:
                    continue
                
                # Get business details
                amenity = tags.get('amenity', '')
                cuisine = tags.get('cuisine', '')
                shop = tags.get('shop', '')
                
                # Get coordinates
                if element['type'] == 'node':
                    lat, lng = element.get('lat'), element.get('lon')
                elif 'center' in element:
                    lat, lng = element['center']['lat'], element['center']['lon']
                else:
                    lat, lng = None, None
                
                # Build address
                address_parts = []
                for addr_key in ['addr:housenumber', 'addr:street', 'addr:city']:
                    if addr_key in tags:
                        address_parts.append(tags[addr_key])
                
                if not address_parts:
                    address = f"{postcode}, Hackney, London"
                else:
                    address = ', '.join(address_parts) + f", {postcode}, London"
                
                # Determine spice priority
                spice_priority = self._calculate_spice_priority(name, cuisine, amenity, shop)
                
                business = BusinessData(
                    name=name,
                    address=address,
                    phone=tags.get('phone'),
                    website=tags.get('website'),
                    cuisine_type=cuisine or amenity or shop,
                    latitude=lat,
                    longitude=lng,
                    postcode=postcode,
                    source="OpenStreetMap",
                    spice_priority=spice_priority
                )
                
                businesses.append(business)
                
        except Exception as e:
            logger.error(f"Error parsing OpenStreetMap data: {str(e)}")
            
        return businesses
    
    def _calculate_spice_priority(self, name: str, cuisine: str, amenity: str, shop: str) -> str:
        """Calculate spice usage priority for businesses"""
        high_spice_keywords = [
            'indian', 'curry', 'tandoori', 'bengali', 'pakistani', 'spice', 'masala',
            'biryani', 'kebab', 'halal', 'thai', 'chinese', 'asian', 'oriental'
        ]
        
        medium_spice_keywords = [
            'restaurant', 'kitchen', 'grill', 'takeaway', 'food', 'cafe'
        ]
        
        text_to_check = f"{name} {cuisine} {amenity} {shop}".lower()
        
        # High priority: Direct spice-heavy cuisine mentions
        for keyword in high_spice_keywords:
            if keyword in text_to_check:
                return "high"
        
        # Medium priority: General food businesses
        for keyword in medium_spice_keywords:
            if keyword in text_to_check:
                return "medium"
        
        return "low"
    
    def extract_google_places_api(self, postcode: str) -> List[BusinessData]:
        """Extract using Google Places API if key available"""
        businesses = []
        
        if not self.google_api_key:
            logger.info("Google Places API key not available, skipping")
            return businesses
        
        try:
            # Get coordinates for search
            location = self.geolocator.geocode(f"{postcode}, Hackney, London, UK")
            if not location:
                return businesses
            
            lat, lng = location.latitude, location.longitude
            
            # Search for spice-heavy restaurants
            search_types = ['indian restaurant', 'asian restaurant', 'chinese restaurant', 'thai restaurant']
            
            for search_type in search_types:
                url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                params = {
                    'location': f"{lat},{lng}",
                    'radius': 1000,
                    'keyword': search_type,
                    'type': 'restaurant',
                    'key': self.google_api_key
                }
                
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK':
                        businesses.extend(self._parse_google_places_data(data, postcode))
                        time.sleep(1)  # Rate limiting
                    else:
                        logger.warning(f"Google Places API error: {data['status']}")
                
        except Exception as e:
            logger.error(f"Google Places API error for {postcode}: {str(e)}")
            
        return businesses
    
    def _parse_google_places_data(self, data: Dict, postcode: str) -> List[BusinessData]:
        """Parse Google Places API response"""
        businesses = []
        
        try:
            for place in data.get('results', []):
                name = place.get('name', '')
                if not name:
                    continue
                
                # Get place details
                location = place.get('geometry', {}).get('location', {})
                rating = place.get('rating')
                price_level = place.get('price_level')
                
                # Convert price level to symbols
                price_symbols = {1: '£', 2: '££', 3: '£££', 4: '££££'}
                price_display = price_symbols.get(price_level, '')
                
                business = BusinessData(
                    name=name,
                    address=place.get('vicinity', f"{postcode}, London"),
                    cuisine_type=', '.join(place.get('types', [])),
                    rating=rating,
                    price_level=price_display,
                    latitude=location.get('lat'),
                    longitude=location.get('lng'),
                    postcode=postcode,
                    source="Google Places API",
                    spice_priority=self._calculate_spice_priority(name, '', '', '')
                )
                
                businesses.append(business)
                
        except Exception as e:
            logger.error(f"Error parsing Google Places data: {str(e)}")
            
        return businesses
    
    def extract_yelp_fusion_api(self, postcode: str) -> List[BusinessData]:
        """Extract using Yelp Fusion API if key available"""
        businesses = []
        
        if not self.yelp_api_key:
            logger.info("Yelp Fusion API key not available, skipping")
            return businesses
        
        try:
            headers = {'Authorization': f'Bearer {self.yelp_api_key}'}
            
            # Search for restaurants in the area
            url = "https://api.yelp.com/v3/businesses/search"
            params = {
                'location': f"{postcode}, Hackney, London, UK",
                'categories': 'restaurants,food',
                'limit': 50,
                'radius': 1000
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                businesses = self._parse_yelp_fusion_data(data, postcode)
                logger.info(f"Yelp Fusion API: Found {len(businesses)} businesses")
            else:
                logger.warning(f"Yelp Fusion API failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Yelp Fusion API error for {postcode}: {str(e)}")
            
        return businesses
    
    def _parse_yelp_fusion_data(self, data: Dict, postcode: str) -> List[BusinessData]:
        """Parse Yelp Fusion API response"""
        businesses = []
        
        try:
            for business_data in data.get('businesses', []):
                name = business_data.get('name', '')
                if not name:
                    continue
                
                # Get location info
                location_data = business_data.get('location', {})
                address = location_data.get('display_address', [])
                address_str = ', '.join(address) if address else f"{postcode}, London"
                
                # Get coordinates
                coordinates = business_data.get('coordinates', {})
                
                # Get categories
                categories = business_data.get('categories', [])
                cuisine_types = [cat.get('title', '') for cat in categories]
                
                business = BusinessData(
                    name=name,
                    address=address_str,
                    phone=business_data.get('phone'),
                    website=business_data.get('url'),
                    cuisine_type=', '.join(cuisine_types),
                    rating=business_data.get('rating'),
                    reviews_count=business_data.get('review_count'),
                    price_level='£' * len(business_data.get('price', '')),
                    latitude=coordinates.get('latitude'),
                    longitude=coordinates.get('longitude'),
                    postcode=postcode,
                    source="Yelp Fusion API",
                    spice_priority=self._calculate_spice_priority(name, ', '.join(cuisine_types), '', '')
                )
                
                businesses.append(business)
                
        except Exception as e:
            logger.error(f"Error parsing Yelp Fusion data: {str(e)}")
            
        return businesses
    
    def enhance_contact_data(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Enhance business data with additional contact information"""
        enhanced = []
        
        for business in businesses:
            try:
                # Generate email from website
                if business.website and not business.email:
                    domain = business.website
                    for prefix in ['https://', 'http://', 'www.']:
                        domain = domain.replace(prefix, '')
                    domain = domain.split('/')[0]
                    if domain and '.' in domain:
                        business.email = f"info@{domain}"
                
                # Get coordinates if missing
                if not business.latitude and business.address:
                    try:
                        location = self.geolocator.geocode(business.address)
                        if location:
                            business.latitude = location.latitude
                            business.longitude = location.longitude
                        time.sleep(0.1)  # Rate limiting for geocoding
                    except Exception as geo_error:
                        logger.debug(f"Geocoding failed for {business.name}: {geo_error}")
                
                enhanced.append(business)
                
            except Exception as e:
                logger.error(f"Error enhancing {business.name}: {str(e)}")
                enhanced.append(business)
                
        return enhanced
    
    def save_results(self, businesses: List[BusinessData]) -> str:
        """Save results with spice priority organization"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # Organize by priority
            high_priority = [b for b in businesses if b.spice_priority == "high"]
            medium_priority = [b for b in businesses if b.spice_priority == "medium"]
            low_priority = [b for b in businesses if b.spice_priority == "low"]
            
            # Sort each priority by name
            high_priority.sort(key=lambda x: x.name)
            medium_priority.sort(key=lambda x: x.name)
            low_priority.sort(key=lambda x: x.name)
            
            # Combine in priority order
            sorted_businesses = high_priority + medium_priority + low_priority
            
            # Convert to DataFrame
            data = []
            for business in sorted_businesses:
                data.append({
                    'Spice Priority': business.spice_priority.upper(),
                    'Business Name': business.name,
                    'Cuisine Type': business.cuisine_type,
                    'Address': business.address,
                    'Postcode': business.postcode,
                    'Phone': business.phone,
                    'Website': business.website,
                    'Email': business.email,
                    'Rating': business.rating,
                    'Price Level': business.price_level,
                    'Reviews Count': business.reviews_count,
                    'Latitude': business.latitude,
                    'Longitude': business.longitude,
                    'Source': business.source
                })
            
            # Save main CSV
            filename = f"data/hackney_spice_businesses_{timestamp}.csv"
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            
            # Save priority-specific files
            high_df = pd.DataFrame([d for d in data if d['Spice Priority'] == 'HIGH'])
            if not high_df.empty:
                high_df.to_csv(f"data/high_priority_spice_businesses_{timestamp}.csv", index=False)
            
            # Save JSON
            json_filename = f"data/hackney_spice_businesses_{timestamp}.json"
            with open(json_filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Save summary report
            self._save_summary_report(businesses, timestamp)
            
            logger.info(f"Saved {len(data)} businesses to {filename}")
            logger.info(f"High priority: {len(high_priority)}, Medium: {len(medium_priority)}, Low: {len(low_priority)}")
            
            return filename
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            return None
    
    def _save_summary_report(self, businesses: List[BusinessData], timestamp: str):
        """Save a summary report of extraction results"""
        try:
            report_lines = [
                f"Hackney Spice Business Extraction Report - {timestamp}",
                "=" * 60,
                f"Total businesses extracted: {len(businesses)}",
                "",
                "Priority Breakdown:",
            ]
            
            priority_counts = {}
            source_counts = {}
            
            for business in businesses:
                priority_counts[business.spice_priority] = priority_counts.get(business.spice_priority, 0) + 1
                source_counts[business.source] = source_counts.get(business.source, 0) + 1
            
            for priority, count in sorted(priority_counts.items()):
                report_lines.append(f"  {priority.upper()}: {count}")
            
            report_lines.extend([
                "",
                "Source Breakdown:",
            ])
            
            for source, count in sorted(source_counts.items()):
                report_lines.append(f"  {source}: {count}")
            
            # Top spice businesses
            high_priority_businesses = [b for b in businesses if b.spice_priority == "high"]
            if high_priority_businesses:
                report_lines.extend([
                    "",
                    "Top High-Priority Spice Businesses:",
                ])
                
                for i, business in enumerate(high_priority_businesses[:10], 1):
                    report_lines.append(f"  {i}. {business.name} - {business.cuisine_type}")
            
            # Save report
            report_filename = f"data/extraction_report_{timestamp}.txt"
            with open(report_filename, 'w') as f:
                f.write('\n'.join(report_lines))
            
            logger.info(f"Summary report saved to {report_filename}")
            
        except Exception as e:
            logger.error(f"Error saving summary report: {str(e)}")
    
    def run_extraction(self, max_postcodes: int = 10):
        """Main extraction process for Hackney spice businesses"""
        logger.info("🚀 Starting Hackney Spice Business Extraction")
        
        postcodes = self.get_hackney_postcodes()[:max_postcodes]
        all_businesses = []
        
        for i, postcode in enumerate(postcodes, 1):
            logger.info(f"📍 Processing {postcode} ({i}/{len(postcodes)})")
            
            try:
                # Method 1: OpenStreetMap (Free, always available)
                osm_businesses = self.extract_overpass_businesses(postcode)
                all_businesses.extend(osm_businesses)
                logger.info(f"  OpenStreetMap: {len(osm_businesses)} businesses")
                
                # Method 2: Google Places API (if key available)
                google_businesses = self.extract_google_places_api(postcode)
                all_businesses.extend(google_businesses)
                if google_businesses:
                    logger.info(f"  Google Places: {len(google_businesses)} businesses")
                
                # Method 3: Yelp Fusion API (if key available)
                yelp_businesses = self.extract_yelp_fusion_api(postcode)
                all_businesses.extend(yelp_businesses)
                if yelp_businesses:
                    logger.info(f"  Yelp Fusion: {len(yelp_businesses)} businesses")
                
                # Rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Error processing {postcode}: {str(e)}")
                continue
        
        # Remove duplicates
        unique_businesses = self._remove_duplicates(all_businesses)
        logger.info(f"📊 Total unique businesses: {len(unique_businesses)}")
        
        # Enhance contact data
        enhanced_businesses = self.enhance_contact_data(unique_businesses)
        
        # Save results
        filename = self.save_results(enhanced_businesses)
        
        logger.info("✅ Hackney extraction completed!")
        return enhanced_businesses, filename
    
    def _remove_duplicates(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Remove duplicate businesses"""
        seen = set()
        unique = []
        
        for business in businesses:
            # Create unique key based on name and approximate location
            name_key = re.sub(r'[^\w\s]', '', business.name.lower()).strip()
            location_key = f"{business.latitude:.3f},{business.longitude:.3f}" if business.latitude else business.address.lower()
            key = f"{name_key}_{location_key}"
            
            if key not in seen:
                seen.add(key)
                unique.append(business)
        
        logger.info(f"🔄 Removed {len(businesses) - len(unique)} duplicates")
        return unique

if __name__ == "__main__":
    try:
        extractor = HackneySpiceExtractor()
        results, filename = extractor.run_extraction(max_postcodes=5)  # Test with 5 postcodes
        
        print(f"\n🎉 HACKNEY SPICE EXTRACTION COMPLETE!")
        print(f"📊 Total businesses: {len(results)}")
        print(f"💾 Data saved to: {filename}")
        
        # Show priority breakdown
        priority_counts = {}
        for business in results:
            priority_counts[business.spice_priority] = priority_counts.get(business.spice_priority, 0) + 1
        
        print(f"\n🌶️ SPICE PRIORITY BREAKDOWN:")
        for priority, count in sorted(priority_counts.items()):
            print(f"  {priority.upper()}: {count} businesses")
        
        # Show top high-priority businesses
        high_priority = [b for b in results if b.spice_priority == "high"]
        if high_priority:
            print(f"\n🔥 TOP HIGH-PRIORITY SPICE BUSINESSES:")
            for i, business in enumerate(high_priority[:10], 1):
                print(f"  {i}. {business.name} - {business.cuisine_type}")
        
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        print(f"❌ Error: {str(e)}") 