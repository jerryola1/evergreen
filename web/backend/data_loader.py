import pandas as pd
from pathlib import Path
import re
from typing import List

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
    
    # Clean up and prepare for JSON
    combined_df = combined_df.drop(columns=['normalized_name', 'address_key', 'dedupe_key', 'info_score'])
    combined_df['Postcode'] = combined_df['Postcode'].str.split().str[0]
    
    # Convert NaN to None for proper JSON representation
    combined_df = combined_df.where(pd.notnull(combined_df), None)

    return combined_df.to_dict('records') 