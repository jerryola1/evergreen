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

# Configure logging for cooking oil extraction
os.makedirs('data/haringey', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/haringey/haringey_oil_extraction.log'),
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
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    postcode: Optional[str] = None
    source: str = "unknown"
    oil_priority: str = "low"  # high, medium, low

class HaringeyOilExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.geolocator = Nominatim(user_agent="haringey_oil_extractor_2025")
        
    def get_haringey_postcodes(self) -> List[str]:
        """Get Haringey postcode districts for oil extraction."""
        haringey_postcodes = [
            "N2", "N4", "N6", "N8", "N10", "N11", "N15", "N17", "N22"
        ]
        
        # Expand to include specific district codes (e.g., N2 0, N2 1...)
        expanded_postcodes = [f"{base} {i}" for base in haringey_postcodes for i in range(10)]
        logger.info(f"Targeting {len(expanded_postcodes)} Haringey postcode areas across {len(haringey_postcodes)} districts for cooking oil customers.")
        return expanded_postcodes
    
    def extract_overpass_businesses(self, postcode: str) -> List[BusinessData]:
        """Extract businesses using OpenStreetMap, focusing on high oil consumption."""
        businesses = []
        try:
            location = self.geolocator.geocode(f"{postcode}, Haringey, London, UK")
            if not location:
                base_postcode = postcode.split()[0]
                location = self.geolocator.geocode(f"{base_postcode}, Haringey, London, UK")
            
            if not location:
                logger.warning(f"Could not geocode {postcode}")
                return []
            
            lat, lng = location.latitude, location.longitude
            logger.info(f"Geocoded {postcode} to {lat:.4f}, {lng:.4f}")
            
            # Overpass query focused on high oil consumption businesses
            overpass_query = f"""
            [out:json][timeout:45];
            (
              // Businesses that fry food are high priority
              nwr["amenity"~"^(fast_food|restaurant|cafe)$"](around:800,{lat},{lng});
              nwr["cuisine"~"fish_and_chips|kebab|chicken|burger|pizza|fried|takeaway|american"](around:800,{lat},{lng});
              
              // Wholesalers who might buy oil in bulk
              nwr["shop"~"wholesale|cash_and_carry"](around:800,{lat},{lng});
            );
            out center meta;
            """
            
            response = self.session.post("http://overpass-api.de/api/interpreter", data=overpass_query, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                businesses = self._parse_overpass_data(data, postcode)
                logger.info(f"OpenStreetMap: Found {len(businesses)} potential oil customers near {postcode}")
            else:
                logger.warning(f"Overpass API failed for {postcode}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Overpass API error for {postcode}: {str(e)}")
            
        return businesses

    def _parse_overpass_data(self, data: Dict, postcode: str) -> List[BusinessData]:
        """Parse OpenStreetMap data with cooking oil priority."""
        businesses = []
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            name = tags.get('name', '').strip()
            if not name or name.lower() in ['unknown', 'unnamed']:
                continue
            
            amenity = tags.get('amenity', '')
            cuisine = tags.get('cuisine', '')
            shop = tags.get('shop', '')
            
            lat = element.get('lat') or element.get('center', {}).get('lat')
            lng = element.get('lon') or element.get('center', {}).get('lon')
            
            address = ', '.join(filter(None, [
                tags.get('addr:housenumber'),
                tags.get('addr:street'),
                f"{postcode}, London"
            ])) or f"{postcode}, Haringey, London"

            oil_priority = self._calculate_oil_priority(name, cuisine, amenity, shop)
            
            businesses.append(BusinessData(
                name=name,
                address=address,
                phone=tags.get('phone'),
                website=tags.get('website'),
                cuisine_type=cuisine or amenity or shop,
                latitude=lat,
                longitude=lng,
                postcode=postcode,
                source="OpenStreetMap",
                oil_priority=oil_priority
            ))
        return businesses

    def _calculate_oil_priority(self, name: str, cuisine: str, amenity: str, shop: str) -> str:
        """Calculate cooking oil usage priority."""
        high_oil_keywords = [
            'fish and chips', 'fried', 'chicken', 'kebab', 'fast_food', 'takeaway', 
            'burger', 'pizza', 'friteur', 'chippy', 'wings'
        ]
        medium_oil_keywords = [
            'restaurant', 'cafe', 'pub', 'diner', 'grill', 'turkish', 'american'
        ]
        
        text_to_check = f"{name} {cuisine} {amenity} {shop}".lower()
        
        if any(keyword in text_to_check for keyword in high_oil_keywords):
            return "high"
        if any(keyword in text_to_check for keyword in medium_oil_keywords):
            return "medium"
        
        return "low"

    def save_results(self, businesses: List[BusinessData]) -> str:
        """Save results with cooking oil priority organization."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Sort by priority then by name
        businesses.sort(key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x.oil_priority], x.name))
        
        df_data = [{
            'Oil Priority': b.oil_priority.upper(),
            'Business Name': b.name,
            'Cuisine Type': b.cuisine_type,
            'Address': b.address,
            'Postcode': b.postcode,
            'Phone': b.phone,
            'Website': b.website,
            'Latitude': b.latitude,
            'Longitude': b.longitude,
            'Source': b.source
        } for b in businesses]
        
        df = pd.DataFrame(df_data)
        
        # Save to data/haringey directory
        filename = f"data/haringey/haringey_cooking_oil_businesses_{timestamp}.csv"
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(df)} businesses to {filename}")
        
        priority_counts = df['Oil Priority'].value_counts()
        logger.info(f"High priority: {priority_counts.get('HIGH', 0)}, Medium: {priority_counts.get('MEDIUM', 0)}, Low: {priority_counts.get('LOW', 0)}")
        
        return filename

    def run_extraction(self):
        """Main extraction process for Haringey cooking oil customers."""
        logger.info("🚀 Starting Haringey Cooking Oil Customer Extraction")
        postcodes = self.get_haringey_postcodes()
        all_businesses = []
        
        for i, postcode in enumerate(postcodes, 1):
            logger.info(f"📍 Processing {postcode} ({i}/{len(postcodes)})")
            try:
                osm_businesses = self.extract_overpass_businesses(postcode)
                all_businesses.extend(osm_businesses)
                time.sleep(2)  # Rate limiting
            except Exception as e:
                logger.error(f"❌ Error processing {postcode}: {str(e)}")
        
        # Remove duplicates
        unique_businesses = list({f"{b.name}_{b.address}": b for b in all_businesses}.values())
        logger.info(f"🔄 Removed {len(all_businesses) - len(unique_businesses)} duplicates")
        logger.info(f"📊 Total unique businesses: {len(unique_businesses)}")
        
        filename = self.save_results(unique_businesses)
        logger.info("✅ Haringey cooking oil extraction completed!")
        return unique_businesses, filename

if __name__ == "__main__":
    try:
        extractor = HaringeyOilExtractor()
        results, filename = extractor.run_extraction()
        
        print("\n🎉 HARINGEY COOKING OIL EXTRACTION COMPLETE!")
        print(f"📊 Total businesses found: {len(results)}")
        print(f"💾 Data saved to: {filename}")
        
        priority_counts = pd.Series([b.oil_priority for b in results]).value_counts()
        print("\n🔥 OIL USAGE PRIORITY BREAKDOWN:")
        print(f"  HIGH (e.g., Fried Chicken, Fish & Chips): {priority_counts.get('high', 0)} businesses")
        print(f"  MEDIUM (e.g., Restaurants, Cafes): {priority_counts.get('medium', 0)} businesses")
        print(f"  LOW (Other): {priority_counts.get('low', 0)} businesses")
        
        high_priority = [b for b in results if b.oil_priority == "high"]
        if high_priority:
            print("\n🎯 TOP HIGH-PRIORITY OIL CUSTOMERS:")
            for i, business in enumerate(high_priority[:10], 1):
                print(f"  {i}. {business.name} - {business.cuisine_type}")
                
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        print(f"❌ An error occurred. Check the log file: data/haringey/haringey_oil_extraction.log") 