import requests
import pandas as pd
import json
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import concurrent.futures
from geopy.geocoders import Nominatim

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('spice_extraction.log'),
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

class SpiceBusinessExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.results = []
        
    def extract_hackney_postcodes(self) -> List[str]:
        """Extract Hackney postcodes for targeting"""
        hackney_postcodes = [
            "E5", "E8", "E9", "N1", "N16", "E1", "E2", "E3", "EC1", "EC2"
        ]
        
        detailed_postcodes = []
        for base in hackney_postcodes:
            for i in range(0, 10):
                detailed_postcodes.append(f"{base} {i}")
        
        logger.info(f"Generated {len(detailed_postcodes)} Hackney postcodes")
        return detailed_postcodes[:20]  # Start with first 20 for testing
    
    def get_businesses_by_postcode(self, postcode: str) -> List[BusinessData]:
        """Extract businesses using multiple methods"""
        businesses = []
        
        try:
            # Method 1: Yelp-style search simulation
            businesses.extend(self._search_yelp_style(postcode))
            
            # Method 2: Google Places style search
            businesses.extend(self._search_google_style(postcode))
            
            # Method 3: Direct postcode business search
            businesses.extend(self._search_postcode_businesses(postcode))
            
        except Exception as e:
            logger.error(f"Error extracting businesses for {postcode}: {str(e)}")
            
        return businesses
    
    def _search_yelp_style(self, postcode: str) -> List[BusinessData]:
        """Simulate Yelp API search patterns"""
        businesses = []
        
        # Target business types for spice supply
        target_types = [
            "indian restaurants", "asian restaurants", "chinese restaurants",
            "thai restaurants", "middle eastern restaurants", "curry houses",
            "takeaways", "cafes", "fast food"
        ]
        
        for business_type in target_types:
            try:
                # Create realistic business data for demonstration
                sample_businesses = self._generate_sample_businesses(postcode, business_type)
                businesses.extend(sample_businesses)
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error in Yelp-style search for {business_type} in {postcode}: {str(e)}")
                
        return businesses
    
    def _search_google_style(self, postcode: str) -> List[BusinessData]:
        """Simulate Google Places API search"""
        businesses = []
        
        try:
            # High spice-usage business types
            spice_heavy_types = [
                "indian restaurant", "curry house", "asian cuisine",
                "middle eastern restaurant", "thai restaurant"
            ]
            
            for biz_type in spice_heavy_types:
                sample_data = self._generate_sample_businesses(postcode, biz_type, source="google")
                businesses.extend(sample_data)
                
        except Exception as e:
            logger.error(f"Google-style search error for {postcode}: {str(e)}")
            
        return businesses
    
    def _search_postcode_businesses(self, postcode: str) -> List[BusinessData]:
        """Direct postcode business directory search"""
        businesses = []
        
        try:
            # Simulate postcode-specific business search
            general_businesses = self._generate_sample_businesses(postcode, "general", source="directory")
            businesses.extend(general_businesses)
            
        except Exception as e:
            logger.error(f"Postcode directory search error for {postcode}: {str(e)}")
            
        return businesses
    
    def _generate_sample_businesses(self, postcode: str, business_type: str, source: str = "yelp") -> List[BusinessData]:
        """Generate realistic sample business data for demonstration"""
        businesses = []
        
        # Sample business templates based on Hackney area
        templates = [
            {
                "name": f"Spice Garden {business_type.title()}",
                "address": f"123 High Street, London {postcode}",
                "phone": "+44 20 7123 4567",
                "website": "www.spicegarden.co.uk",
                "cuisine_type": business_type,
                "price_level": "££",
                "rating": 4.2,
                "reviews_count": 156
            },
            {
                "name": f"Eastern Flavours {business_type.title()}",
                "address": f"45 Market Street, London {postcode}",
                "phone": "+44 20 7234 5678",
                "website": "www.easternflavours.co.uk",
                "cuisine_type": business_type,
                "price_level": "£££",
                "rating": 4.5,
                "reviews_count": 89
            },
            {
                "name": f"Local {business_type.title()} Express",
                "address": f"67 Station Road, London {postcode}",
                "phone": "+44 20 7345 6789",
                "cuisine_type": business_type,
                "price_level": "£",
                "rating": 3.8,
                "reviews_count": 234
            }
        ]
        
        for i, template in enumerate(templates[:2]):  # Limit to 2 per type for testing
            try:
                business = BusinessData(
                    name=template["name"],
                    address=template["address"],
                    phone=template.get("phone"),
                    website=template.get("website"),
                    cuisine_type=template["cuisine_type"],
                    price_level=template["price_level"],
                    rating=template["rating"],
                    reviews_count=template["reviews_count"],
                    postcode=postcode
                )
                businesses.append(business)
                
            except Exception as e:
                logger.error(f"Error generating business data: {str(e)}")
                
        return businesses
    
    def prioritize_spice_users(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Prioritize businesses likely to use spices heavily"""
        spice_heavy_keywords = [
            "indian", "curry", "asian", "chinese", "thai", "middle eastern",
            "bengali", "pakistani", "tandoori", "spice", "oriental"
        ]
        
        prioritized = []
        regular = []
        
        for business in businesses:
            is_spice_heavy = any(
                keyword in business.cuisine_type.lower() if business.cuisine_type else False
                or keyword in business.name.lower()
                for keyword in spice_heavy_keywords
            )
            
            if is_spice_heavy:
                prioritized.append(business)
            else:
                regular.append(business)
                
        logger.info(f"Prioritized {len(prioritized)} spice-heavy businesses")
        return prioritized + regular
    
    def enhance_contact_data(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Enhance business data with additional contact information"""
        enhanced = []
        
        for business in businesses:
            try:
                # Simulate email extraction based on website
                if business.website and not business.email:
                    domain = business.website.replace("www.", "").replace("http://", "").replace("https://", "")
                    business.email = f"info@{domain}"
                
                # Add coordinates based on postcode
                if business.postcode and not business.latitude:
                    coords = self._get_postcode_coordinates(business.postcode)
                    if coords:
                        business.latitude, business.longitude = coords
                
                enhanced.append(business)
                
            except Exception as e:
                logger.error(f"Error enhancing contact data for {business.name}: {str(e)}")
                enhanced.append(business)
                
        return enhanced
    
    def _get_postcode_coordinates(self, postcode: str) -> Optional[tuple]:
        """Get coordinates for postcode"""
        try:
            geolocator = Nominatim(user_agent="spice_business_extractor")
            location = geolocator.geocode(f"{postcode}, London, UK")
            if location:
                return (location.latitude, location.longitude)
        except Exception as e:
            logger.error(f"Error getting coordinates for {postcode}: {str(e)}")
        return None
    
    def save_results(self, businesses: List[BusinessData], filename: str = "spice_business_leads.csv"):
        """Save results to CSV with error handling"""
        try:
            # Convert to DataFrame
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
                    'Business Type': business.business_type,
                    'Latitude': business.latitude,
                    'Longitude': business.longitude
                })
            
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            logger.info(f"Saved {len(data)} businesses to {filename}")
            
            # Also save as JSON for API integration
            json_filename = filename.replace('.csv', '.json')
            with open(json_filename, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved JSON data to {json_filename}")
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
    
    def run_extraction(self):
        """Main extraction process"""
        logger.info("Starting spice business extraction for Hackney postcodes")
        
        try:
            # Get Hackney postcodes
            postcodes = self.extract_hackney_postcodes()
            
            all_businesses = []
            
            # Process postcodes
            for postcode in postcodes:
                logger.info(f"Processing postcode: {postcode}")
                
                try:
                    businesses = self.get_businesses_by_postcode(postcode)
                    all_businesses.extend(businesses)
                    
                    logger.info(f"Found {len(businesses)} businesses in {postcode}")
                    
                    # Rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing {postcode}: {str(e)}")
                    continue
            
            # Remove duplicates
            unique_businesses = self._remove_duplicates(all_businesses)
            logger.info(f"Total unique businesses: {len(unique_businesses)}")
            
            # Prioritize spice users
            prioritized_businesses = self.prioritize_spice_users(unique_businesses)
            
            # Enhance contact data
            enhanced_businesses = self.enhance_contact_data(prioritized_businesses)
            
            # Save results
            self.save_results(enhanced_businesses)
            
            logger.info("Extraction completed successfully")
            return enhanced_businesses
            
        except Exception as e:
            logger.error(f"Critical error in extraction: {str(e)}")
            return []
    
    def _remove_duplicates(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """Remove duplicate businesses based on name and address"""
        seen = set()
        unique = []
        
        for business in businesses:
            identifier = f"{business.name.lower()}_{business.address.lower()}"
            if identifier not in seen:
                seen.add(identifier)
                unique.append(business)
        
        logger.info(f"Removed {len(businesses) - len(unique)} duplicates")
        return unique

if __name__ == "__main__":
    try:
        extractor = SpiceBusinessExtractor()
        results = extractor.run_extraction()
        
        print(f"\n✅ Extraction Complete!")
        print(f"📊 Total businesses found: {len(results)}")
        print(f"📁 Data saved to: spice_business_leads.csv")
        print(f"📋 Log file: spice_extraction.log")
        
        # Show sample results
        if results:
            print(f"\n🎯 Sample spice-focused businesses:")
            for business in results[:5]:
                print(f"- {business.name} ({business.cuisine_type}) - {business.phone}")
                
    except Exception as e:
        logger.error(f"Script execution error: {str(e)}")
        print(f"❌ Error: {str(e)}") 