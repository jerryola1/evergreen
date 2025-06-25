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

            # Standardize Borough column
            if 'Borough' not in df.columns:
                if 'hackney' in str(file).lower(): df['Borough'] = 'Hackney'
                elif 'haringey' in str(file).lower(): df['Borough'] = 'Haringey'
                else: df['Borough'] = 'Other'
            
            data_frames.append(df)
        except Exception:
            continue

    if not data_frames:
        return []

    combined_df = pd.concat(data_frames, ignore_index=True)

    # --- Professional Deduplication ---
    def normalize_key_text(text):
        return re.sub(r'[^a-z0-9]', '', str(text).lower())

    combined_df['normalized_name'] = combined_df['Business Name'].apply(normalize_key_text)
    combined_df['address_key'] = combined_df['Address'].str.split(',').str[0].apply(normalize_key_text)
    combined_df['dedupe_key'] = combined_df['normalized_name'] + '_' + combined_df['address_key']

    combined_df['info_score'] = combined_df['Phone'].notna().astype(int) + \
                                combined_df['Website'].notna().astype(int) + \
                                (combined_df['Priority'] == 'HIGH').astype(int)

    combined_df.sort_values('info_score', ascending=False, inplace=True)
    combined_df.drop_duplicates(subset=['dedupe_key'], keep='first', inplace=True)
    
    # Add contact tracking columns if they don't exist
    if 'Contacted' not in combined_df.columns:
        combined_df['Contacted'] = False
    if 'Contact_Date' not in combined_df.columns:
        combined_df['Contact_Date'] = ''
    if 'Contact_Notes' not in combined_df.columns:
        combined_df['Contact_Notes'] = ''
    
    # Clean up and prepare for JSON
    combined_df = combined_df.drop(columns=['normalized_name', 'address_key', 'dedupe_key', 'info_score'])
    combined_df['Postcode'] = combined_df['Postcode'].str.split().str[0]
    
    # Convert NaN to None for proper JSON representation
    combined_df = combined_df.where(pd.notnull(combined_df), None)

    return combined_df.to_dict('records')


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