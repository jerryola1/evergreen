import pandas as pd
from pathlib import Path
import re
from typing import List, Optional
from datetime import datetime

def load_and_clean_data() -> List[dict]:
    """
    Loads all business data from CSV files, cleans it, and performs professional deduplication.
    Returns a list of dictionaries, ready to be served as JSON.
    """
    data_dir = Path(__file__).parent.parent.parent.joinpath('data')
    data_frames = []

    all_files = list(data_dir.rglob("*_businesses_*.csv"))
    if not all_files:
        return []

    def get_borough_from_path(file_path: Path) -> str:
        """Extract borough name from file path dynamically."""
        # Get the parent folder name (borough folder)
        borough_folder = file_path.parent.name
        
        # Convert folder name to display name
        # Replace underscores with spaces and title case
        borough_name = borough_folder.replace('_', ' ').title()
        
        # Handle special cases for better display
        if 'hammersmith' in borough_folder.lower():
            return 'Hammersmith & Fulham'
        elif 'richmond' in borough_folder.lower():
            return 'Richmond upon Thames'
        elif 'kingston' in borough_folder.lower():
            return 'Kingston upon Thames'
        
        return borough_name

    for file in all_files:
        try:
            df = pd.read_csv(file)
            
            # Standardize Priority column
            if 'spice' in file.stem.lower():
                df['Lead Type'] = 'Spice'
                df.rename(columns={'Spice Priority': 'Priority'}, inplace=True)
            elif 'oil' in file.stem.lower():
                df['Lead Type'] = 'Cooking Oil'
                df.rename(columns={'Oil Priority': 'Priority'}, inplace=True)
            else:
                df['Lead Type'] = 'General'
                if 'Spice Priority' in df.columns: df.rename(columns={'Spice Priority': 'Priority'}, inplace=True)
                elif 'Oil Priority' in df.columns: df.rename(columns={'Oil Priority': 'Priority'}, inplace=True)
                elif 'Priority' not in df.columns: df['Priority'] = 'LOW'

            # Dynamically set Borough from folder path
            if 'Borough' not in df.columns:
                df['Borough'] = get_borough_from_path(file)
            
            data_frames.append(df)
        except Exception:
            continue

    if not data_frames:
        return []

    combined_df = pd.concat(data_frames, ignore_index=True)

    # --- Improved Deduplication ---
    def normalize_business_name(text):
        # Remove common business suffixes and normalize
        text = str(text).lower().strip()
        # Remove common endings
        for suffix in [' ltd', ' limited', ' restaurant', ' cafe', ' takeaway', ' kitchen', ' grill']:
            if text.endswith(suffix):
                text = text[:-len(suffix)].strip()
        # Remove all non-alphanumeric except spaces
        text = re.sub(r'[^a-z0-9\s]', '', text)
        # Remove extra spaces
        text = re.sub(r'\s+', '', text)
        return text

    def extract_street_name(address):
        # Extract just the street name/number for better matching
        if pd.isna(address):
            return ''
        address = str(address).lower()
        # Take first part before first comma and normalize
        street_part = address.split(',')[0].strip()
        # Remove numbers and normalize to just street name
        street_part = re.sub(r'\d+[a-z]*\s*', '', street_part)  # Remove numbers
        street_part = re.sub(r'[^a-z\s]', '', street_part)  # Keep only letters and spaces
        street_part = re.sub(r'\s+', '', street_part)  # Remove spaces
        return street_part

    # Create better deduplication keys
    combined_df['normalized_name'] = combined_df['Business Name'].apply(normalize_business_name)
    combined_df['street_key'] = combined_df['Address'].apply(extract_street_name)
    combined_df['dedupe_key'] = combined_df['normalized_name'] + '_' + combined_df['street_key']

    # Add scoring to keep the best record for each duplicate
    combined_df['info_score'] = (
        combined_df['Phone'].notna().astype(int) + 
        combined_df['Website'].notna().astype(int) + 
        combined_df['Email'].notna().astype(int) + 
        (combined_df['Priority'] == 'HIGH').astype(int) * 2 +
        (combined_df['Priority'] == 'MEDIUM').astype(int)
    )

    # Sort by score (best first) and deduplicate
    combined_df.sort_values(['info_score', 'Business Name'], ascending=[False, True], inplace=True)
    
    # More aggressive deduplication - also dedupe by name only if very similar
    combined_df_deduped = combined_df.drop_duplicates(subset=['dedupe_key'], keep='first')
    
    # Additional pass: remove businesses with identical names (regardless of address)
    combined_df_deduped = combined_df_deduped.drop_duplicates(subset=['normalized_name'], keep='first')
    
    # Add contact tracking columns if they don't exist
    if 'Contacted' not in combined_df_deduped.columns:
        combined_df_deduped['Contacted'] = False
    if 'Contact_Date' not in combined_df_deduped.columns:
        combined_df_deduped['Contact_Date'] = ''
    if 'Contact_Notes' not in combined_df_deduped.columns:
        combined_df_deduped['Contact_Notes'] = ''
    
    # Clean up and prepare for JSON
    combined_df_deduped = combined_df_deduped.drop(columns=['normalized_name', 'street_key', 'dedupe_key', 'info_score'])
    combined_df_deduped['Postcode'] = combined_df_deduped['Postcode'].str.split().str[0]
    
    # Convert NaN to None for proper JSON representation
    combined_df_deduped = combined_df_deduped.where(pd.notnull(combined_df_deduped), None)

    return combined_df_deduped.to_dict('records')


def update_contact_status(business_name: str, contacted: bool, contact_notes: Optional[str] = None) -> bool:
    """
    Updates the contact status for a specific business in CSV files.
    Returns True if successful, False if business not found.
    """
    data_dir = Path(__file__).parent.parent.parent.joinpath('data')
    all_files = list(data_dir.rglob("*_businesses_*.csv"))
    
    if not all_files:
        return False
    
    business_updated = False
    contact_date = datetime.now().strftime('%Y-%m-%d') if contacted else None
    
    for file in all_files:
        try:
            df = pd.read_csv(file)
            
            # Find the business by name
            business_mask = df['Business Name'] == business_name
            if business_mask.any():
                # Add contact columns if they don't exist - fill with defaults
                if 'Contacted' not in df.columns:
                    df['Contacted'] = False
                if 'Contact_Date' not in df.columns:
                    df['Contact_Date'] = ''
                if 'Contact_Notes' not in df.columns:
                    df['Contact_Notes'] = ''
                
                # Update the contact information for the specific business
                df.loc[business_mask, 'Contacted'] = contacted
                df.loc[business_mask, 'Contact_Date'] = contact_date if contact_date else ''
                df.loc[business_mask, 'Contact_Notes'] = contact_notes if contact_notes else ''
                
                # Save back to CSV with new columns
                df.to_csv(file, index=False)
                business_updated = True
                print(f"✅ Updated {business_name} in {file.name}")
                # Don't break - continue to update ALL files that contain this business
                
        except Exception as e:
            print(f"Error updating {file}: {e}")
            continue
    
    return business_updated 