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
        logging.FileHandler('data/haringey/haringey_spice_extraction.log'),
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

class HaringeySpiceExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # API Keys (optional)
        self.google_api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        self.yelp_api_key = os.getenv('YELP_API_KEY')
        
        self.geolocator = Nominatim(user_agent="haringey_spice_extractor_2025")
        self.results = []
        
        logger.info(f"Google API Key: {'✅ Available' if self.google_api_key else '❌ Not set'}")
        logger.info(f"Yelp API Key: {'✅ Available' if self.yelp_api_key else '❌ Not set'}")
        
    def get_haringey_postcodes(self) -> List[str]:
        """Get Haringey postcode districts as provided by user"""
        haringey_postcodes = [
            "N2",   # East Finchley (part)
            "N4",   # Finsbury Park / Harringay (part)
            "N6",   # Highgate (shared with Camden and Islington)
            "N8",   # Hornsey / Crouch End / Harringay (part)
            "N10",  # Muswell Hill (part)
            "N11",  # New Southgate (part)
            "N15",  # South Tottenham / Seven Sisters
            "N17",  # Tottenham
            "N22",  # Wood Green / Turnpike Lane / Bowes Park (part)
        ]
        
        # Expand to include specific district codes
        expanded_postcodes = []
        for base in haringey_postcodes:
            for i in range(10):
                expanded_postcodes.append(f"{base} {i}")
        
        logger.info(f"Targeting {len(expanded_postcodes)} Haringey postcodes across {len(haringey_postcodes)} districts")
        return expanded_postcodes
    
    def extract_overpass_businesses(self, postcode: str) -> List[BusinessData]:
        """Extract businesses using OpenStreetMap Overpass API"""
        businesses = []
        
        try:
            # Get coordinates for postcode area
            location = self.geolocator.geocode(f"{postcode}, Haringey, London, UK")
            if not location:
                # Try without specific district number
                base_postcode = postcode.split()[0]
                location = self.geolocator.geocode(f"{base_postcode}, Haringey, London, UK")
                
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
              nwr["cuisine"~"indian|asian|chinese|thai|middle_eastern|curry|bengali|pakistani|nepalese|sri_lankan|turkish|african"](around:800,{lat},{lng});
              
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
                    address = f"{postcode}, Haringey, London"
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
        """Calculate spice usage priority for businesses (enhanced for diverse Haringey)"""
        high_spice_keywords = [
            'indian', 'curry', 'tandoori', 'bengali', 'pakistani', 'spice', 'masala',
            'biryani', 'kebab', 'halal', 'thai', 'chinese', 'asian', 'oriental',
            'turkish', 'african', 'ethiopian', 'moroccan', 'middle_eastern',
            'sri_lankan', 'nepalese', 'vietnamese', 'korean', 'japanese'
        ]
        
        medium_spice_keywords = [
            'restaurant', 'kitchen', 'grill', 'takeaway', 'food', 'cafe',
            'pizza', 'mediterranean', 'caribbean', 'jamaican'
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
            filename = f"data/haringey/haringey_spice_businesses_{timestamp}.csv"
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            
            # Save priority-specific files
            high_df = pd.DataFrame([d for d in data if d['Spice Priority'] == 'HIGH'])
            if not high_df.empty:
                high_df.to_csv(f"data/haringey/haringey_high_priority_spice_{timestamp}.csv", index=False)
            
            # Save JSON
            json_filename = f"data/haringey/haringey_spice_businesses_{timestamp}.json"
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
                f"Haringey Spice Business Extraction Report - {timestamp}",
                "=" * 60,
                f"Total businesses extracted: {len(businesses)}",
                "",
                "Haringey Postcode Districts Covered:",
                "  N2 – East Finchley (part)",
                "  N4 – Finsbury Park / Harringay (part)", 
                "  N6 – Highgate (shared with Camden and Islington)",
                "  N8 – Hornsey / Crouch End / Harringay (part)",
                "  N10 – Muswell Hill (part)",
                "  N11 – New Southgate (part)",
                "  N15 – South Tottenham / Seven Sisters",
                "  N17 – Tottenham",
                "  N22 – Wood Green / Turnpike Lane / Bowes Park (part)",
                "",
                "Priority Breakdown:",
            ]
            
            priority_counts = {}
            source_counts = {}
            postcode_counts = {}
            
            for business in businesses:
                priority_counts[business.spice_priority] = priority_counts.get(business.spice_priority, 0) + 1
                source_counts[business.source] = source_counts.get(business.source, 0) + 1
                
                # Count by base postcode
                base_postcode = business.postcode.split()[0] if business.postcode else "Unknown"
                postcode_counts[base_postcode] = postcode_counts.get(base_postcode, 0) + 1
            
            for priority, count in sorted(priority_counts.items()):
                report_lines.append(f"  {priority.upper()}: {count}")
            
            report_lines.extend([
                "",
                "Source Breakdown:",
            ])
            
            for source, count in sorted(source_counts.items()):
                report_lines.append(f"  {source}: {count}")
            
            report_lines.extend([
                "",
                "Businesses by Postcode District:",
            ])
            
            for postcode, count in sorted(postcode_counts.items()):
                report_lines.append(f"  {postcode}: {count}")
            
            # Top spice businesses
            high_priority_businesses = [b for b in businesses if b.spice_priority == "high"]
            if high_priority_businesses:
                report_lines.extend([
                    "",
                    "Top High-Priority Spice Businesses in Haringey:",
                ])
                
                for i, business in enumerate(high_priority_businesses[:15], 1):
                    postcode_area = business.postcode.split()[0] if business.postcode else "Unknown"
                    report_lines.append(f"  {i}. {business.name} ({postcode_area}) - {business.cuisine_type}")
            
            # Save report
            report_filename = f"data/haringey/haringey_extraction_report_{timestamp}.txt"
            with open(report_filename, 'w') as f:
                f.write('\n'.join(report_lines))
            
            logger.info(f"Haringey summary report saved to {report_filename}")
            
        except Exception as e:
            logger.error(f"Error saving summary report: {str(e)}")
    
    def run_extraction(self, max_postcodes: int = 15):
        """Main extraction process for Haringey spice businesses"""
        logger.info("🚀 Starting Haringey Spice Business Extraction")
        
        postcodes = self.get_haringey_postcodes()[:max_postcodes]
        all_businesses = []
        
        for i, postcode in enumerate(postcodes, 1):
            logger.info(f"📍 Processing {postcode} ({i}/{len(postcodes)})")
            
            try:
                # OpenStreetMap (Free, always available)
                osm_businesses = self.extract_overpass_businesses(postcode)
                all_businesses.extend(osm_businesses)
                logger.info(f"  OpenStreetMap: {len(osm_businesses)} businesses")
                
                # Rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Error processing {postcode}: {str(e)}")
                continue
        
        # Remove duplicates
        unique_businesses = self._remove_duplicates(all_businesses)
        logger.info(f"📊 Total unique businesses: {len(unique_businesses)}")
        
        # Save results
        filename = self.save_results(unique_businesses)
        
        logger.info("✅ Haringey extraction completed!")
        return unique_businesses, filename
    
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
        extractor = HaringeySpiceExtractor()
        results, filename = extractor.run_extraction(max_postcodes=15)  # Test with 15 postcodes
        
        print(f"\n🎉 HARINGEY SPICE EXTRACTION COMPLETE!")
        print(f"📊 Total businesses: {len(results)}")
        print(f"💾 Data saved to: {filename}")
        
        # Show priority breakdown
        priority_counts = {}
        postcode_counts = {}
        
        for business in results:
            priority_counts[business.spice_priority] = priority_counts.get(business.spice_priority, 0) + 1
            base_postcode = business.postcode.split()[0] if business.postcode else "Unknown"
            postcode_counts[base_postcode] = postcode_counts.get(base_postcode, 0) + 1
        
        print(f"\n🌶️ SPICE PRIORITY BREAKDOWN:")
        for priority, count in sorted(priority_counts.items()):
            print(f"  {priority.upper()}: {count} businesses")
        
        print(f"\n📍 BUSINESSES BY POSTCODE DISTRICT:")
        for postcode, count in sorted(postcode_counts.items()):
            print(f"  {postcode}: {count} businesses")
        
        # Show top high-priority businesses
        high_priority = [b for b in results if b.spice_priority == "high"]
        if high_priority:
            print(f"\n🔥 TOP HIGH-PRIORITY SPICE BUSINESSES:")
            for i, business in enumerate(high_priority[:10], 1):
                postcode_area = business.postcode.split()[0] if business.postcode else "Unknown"
                print(f"  {i}. {business.name} ({postcode_area}) - {business.cuisine_type}")
        
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        print(f"❌ Error: {str(e)}") 