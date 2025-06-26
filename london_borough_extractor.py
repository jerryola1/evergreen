#!/usr/bin/env python3

import requests
import pandas as pd
import json
import time
import logging
import os
import argparse
from typing import Dict, List, Optional
from dataclasses import dataclass
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
import re
from pathlib import Path

# Load environment variables
load_dotenv()

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
    priority: str = "low"  # high, medium, low
    lead_type: str = "general"  # cooking_oil, spice, general

class LondonBoroughExtractor:
    def __init__(self, borough_name: str):
        self.borough_name = borough_name
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.geolocator = Nominatim(user_agent=f"london_{borough_name.lower()}_extractor_2025")
        
        # Setup logging
        os.makedirs(f'data/{borough_name.lower()}', exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'data/{borough_name.lower()}/{borough_name.lower()}_extraction.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def get_borough_postcodes(self) -> List[str]:
        """Get postcode districts for the borough."""
        # Major London postcodes by borough
        borough_postcodes = {
            'westminster': ['W1', 'SW1', 'W2', 'WC1', 'WC2'],
            'camden': ['NW1', 'NW3', 'WC1', 'N1', 'N7'],
            'islington': ['N1', 'N4', 'N5', 'N7', 'N19'],
            'tower_hamlets': ['E1', 'E2', 'E3', 'E14', 'E1W'],
            'southwark': ['SE1', 'SE5', 'SE15', 'SE16', 'SE17'],
            'lambeth': ['SE1', 'SE11', 'SE24', 'SE27', 'SW2', 'SW4', 'SW8', 'SW9'],
            'wandsworth': ['SW8', 'SW11', 'SW12', 'SW15', 'SW17', 'SW18', 'SW19'],
            'hammersmith_fulham': ['W6', 'W12', 'W14', 'SW6', 'SW10'],
            'barnet': ['EN4', 'EN5', 'N2', 'N3', 'N11', 'N12', 'N14', 'N20', 'NW4', 'NW7'],
            'enfield': ['EN1', 'EN2', 'EN3', 'N9', 'N13', 'N14', 'N18', 'N21'],
            'waltham_forest': ['E4', 'E10', 'E11', 'E17', 'N15'],
            'newham': ['E6', 'E7', 'E12', 'E13', 'E15', 'E16'],
            'greenwich': ['SE3', 'SE7', 'SE8', 'SE9', 'SE10', 'SE18'],
            'lewisham': ['SE4', 'SE6', 'SE12', 'SE13', 'SE14', 'SE23', 'BR1'],
            'bromley': ['BR1', 'BR2', 'BR3', 'BR4', 'BR5', 'BR6', 'BR7', 'SE9', 'SE19', 'SE20'],
            'croydon': ['CR0', 'CR2', 'CR4', 'CR7', 'CR8', 'SE19', 'SE25', 'SW16'],
            'brent': ['NW2', 'NW6', 'NW9', 'NW10', 'HA0', 'HA9'],
            'ealing': ['W3', 'W5', 'W7', 'W13', 'UB1', 'UB2', 'UB6'],
            'hounslow': ['TW3', 'TW4', 'TW5', 'TW13', 'TW14', 'UB3', 'UB4'],
            'richmond': ['TW1', 'TW2', 'TW9', 'TW10', 'SW13', 'SW14', 'SW15', 'KT2'],
            'kingston': ['KT1', 'KT2', 'KT3', 'KT4', 'KT5', 'KT6', 'SW15', 'SW20']
        }
        
        base_postcodes = borough_postcodes.get(self.borough_name.lower(), [])
        if not base_postcodes:
            self.logger.error(f"No postcodes defined for {self.borough_name}")
            return []
            
        # Expand to include district codes (e.g., W1 0, W1 1...)
        expanded_postcodes = []
        for base in base_postcodes:
            for i in range(10):
                expanded_postcodes.append(f"{base} {i}")
        
        self.logger.info(f"Targeting {len(expanded_postcodes)} postcode areas across {len(base_postcodes)} districts in {self.borough_name}")
        return expanded_postcodes
    
    def extract_overpass_businesses(self, postcode: str) -> List[BusinessData]:
        """Extract businesses using OpenStreetMap, prioritizing oil customers with spice businesses."""
        businesses = []
        try:
            location = self.geolocator.geocode(f"{postcode}, {self.borough_name}, London, UK")
            if not location:
                base_postcode = postcode.split()[0]
                location = self.geolocator.geocode(f"{base_postcode}, {self.borough_name}, London, UK")
            
            if not location:
                self.logger.warning(f"Could not geocode {postcode}")
                return []
            
            lat, lng = location.latitude, location.longitude
            self.logger.info(f"Geocoded {postcode} to {lat:.4f}, {lng:.4f}")
            
            # Overpass query focused on cooking oil + spice businesses
            overpass_query = f"""
            [out:json][timeout:45];
            (
              // HIGH PRIORITY: Oil-heavy businesses (fish & chips, fried food, fast food)
              nwr["amenity"~"^(fast_food|restaurant|cafe)$"](around:800,{lat},{lng});
              nwr["cuisine"~"fish_and_chips|kebab|chicken|burger|pizza|fried|takeaway|american"](around:800,{lat},{lng});
              
              // SPICE BUSINESSES: Indian, Chinese, Thai, etc.
              nwr["cuisine"~"indian|chinese|thai|asian|curry|bengali|pakistani|turkish|mediterranean"](around:800,{lat},{lng});
              
              // Wholesalers and suppliers
              nwr["shop"~"wholesale|cash_and_carry|convenience|supermarket"](around:800,{lat},{lng});
            );
            out center meta;
            """
            
            response = self.session.post("http://overpass-api.de/api/interpreter", data=overpass_query, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                businesses = self._parse_overpass_data(data, postcode)
                self.logger.info(f"OpenStreetMap: Found {len(businesses)} businesses near {postcode}")
            else:
                self.logger.warning(f"Overpass API failed for {postcode}: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Overpass API error for {postcode}: {str(e)}")
            
        time.sleep(1)  # Rate limiting
        return businesses

    def _parse_overpass_data(self, data: Dict, postcode: str) -> List[BusinessData]:
        """Parse OpenStreetMap data with cooking oil priority and spice classification."""
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
            ])) or f"{postcode}, {self.borough_name}, London"

            priority, lead_type = self._calculate_priority_and_type(name, cuisine, amenity, shop)
            
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
                priority=priority,
                lead_type=lead_type
            ))
        return businesses

    def _calculate_priority_and_type(self, name: str, cuisine: str, amenity: str, shop: str) -> tuple:
        """Calculate priority and lead type (cooking oil priority)."""
        text_to_check = f"{name} {cuisine} {amenity} {shop}".lower()
        
        # COOKING OIL (PRIORITY) - High oil consumption businesses
        high_oil_keywords = [
            'fish and chips', 'fried', 'chicken', 'kebab', 'fast_food', 'takeaway', 
            'burger', 'pizza', 'friteur', 'chippy', 'wings', 'kfc', 'mcdonald'
        ]
        medium_oil_keywords = [
            'restaurant', 'cafe', 'pub', 'diner', 'grill', 'turkish', 'american', 'brasserie'
        ]
        
        # SPICE BUSINESSES - High spice usage
        high_spice_keywords = [
            'indian', 'curry', 'tandoori', 'bengali', 'pakistani', 'thai', 'chinese', 
            'asian', 'kebab', 'halal', 'mediterranean', 'turkish', 'moroccan', 'lebanese'
        ]
        medium_spice_keywords = [
            'restaurant', 'kitchen', 'grill', 'cafe', 'takeaway'
        ]
        
        # Determine lead type and priority
        if any(keyword in text_to_check for keyword in high_oil_keywords):
            return "high", "cooking_oil"
        elif any(keyword in text_to_check for keyword in high_spice_keywords):
            return "high", "spice"
        elif any(keyword in text_to_check for keyword in medium_oil_keywords):
            return "medium", "cooking_oil"
        elif any(keyword in text_to_check for keyword in medium_spice_keywords):
            return "medium", "spice"
        else:
            return "low", "general"

    def save_results(self, businesses: List[BusinessData]) -> str:
        """Save results with cooking oil priority organization."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Sort by lead type (oil first), then priority, then name
        businesses.sort(key=lambda x: (
            {"cooking_oil": 0, "spice": 1, "general": 2}[x.lead_type],
            {"high": 0, "medium": 1, "low": 2}[x.priority], 
            x.name
        ))
        
        df_data = [{
            'Priority': b.priority.upper(),
            'Lead Type': b.lead_type.title().replace('_', ' '),
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
        
        # Save to data/{borough} directory
        filename = f"data/{self.borough_name.lower()}/{self.borough_name.lower()}_businesses_{timestamp}.csv"
        df.to_csv(filename, index=False)
        self.logger.info(f"💾 Saved {len(df)} businesses to {filename}")
        
        # Log statistics
        priority_counts = df['Priority'].value_counts()
        lead_type_counts = df['Lead Type'].value_counts()
        
        self.logger.info(f"📊 Priority breakdown - High: {priority_counts.get('HIGH', 0)}, Medium: {priority_counts.get('MEDIUM', 0)}, Low: {priority_counts.get('LOW', 0)}")
        self.logger.info(f"🎯 Lead types - Cooking Oil: {lead_type_counts.get('Cooking Oil', 0)}, Spice: {lead_type_counts.get('Spice', 0)}, General: {lead_type_counts.get('General', 0)}")
        
        return filename

    def run_extraction(self):
        """Main extraction process for the borough."""
        self.logger.info(f"🚀 Starting {self.borough_name.title()} Business Extraction (Cooking Oil Priority + Spices)")
        postcodes = self.get_borough_postcodes()
        all_businesses = []
        
        for i, postcode in enumerate(postcodes, 1):
            self.logger.info(f"⏳ Processing {postcode} ({i}/{len(postcodes)})")
            businesses = self.extract_overpass_businesses(postcode)
            all_businesses.extend(businesses)
            
            # Progress update every 10 postcodes
            if i % 10 == 0:
                self.logger.info(f"📈 Progress: {i}/{len(postcodes)} postcodes processed, {len(all_businesses)} businesses found")
        
        if all_businesses:
            filename = self.save_results(all_businesses)
            self.logger.info(f"✅ {self.borough_name.title()} extraction completed! {len(all_businesses)} businesses saved to {filename}")
        else:
            self.logger.warning(f"❌ No businesses found for {self.borough_name}")

def main():
    # Define borough batches
    BOROUGH_BATCHES = {
        1: ['Westminster', 'Camden', 'Islington', 'Tower_Hamlets'],
        2: ['Southwark', 'Lambeth', 'Wandsworth', 'Hammersmith_Fulham'],
        3: ['Barnet', 'Enfield', 'Waltham_Forest', 'Newham'],
        4: ['Greenwich', 'Lewisham', 'Bromley', 'Croydon'],
        5: ['Brent', 'Ealing', 'Hounslow', 'Richmond', 'Kingston']
    }
    
    parser = argparse.ArgumentParser(description='Extract London borough businesses (Cooking Oil Priority + Spices)')
    parser.add_argument('--batch', type=int, choices=[1, 2, 3, 4, 5], required=True, 
                       help='Batch number to extract (1-5)')
    parser.add_argument('--borough', type=str, 
                       help='Extract single borough instead of batch')
    
    args = parser.parse_args()
    
    if args.borough:
        boroughs = [args.borough]
    else:
        boroughs = BOROUGH_BATCHES[args.batch]
    
    print(f"🌟 London Borough Business Extractor")
    print(f"🎯 Priority: Cooking Oil businesses (with Spice businesses included)")
    print(f"📦 Batch {args.batch}: {', '.join(boroughs)}")
    print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    for borough in boroughs:
        print(f"\n🏙️  Starting extraction for {borough}...")
        extractor = LondonBoroughExtractor(borough)
        extractor.run_extraction()
        print(f"✅ {borough} completed!")
        
        # Brief pause between boroughs
        time.sleep(2)
    
    print(f"\n🎉 All extractions completed for Batch {args.batch}!")
    print(f"⏰ Finished at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 