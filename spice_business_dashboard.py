import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import json
import os
from pathlib import Path
import numpy as np
from datetime import datetime
import altair as alt
import re

# Page configuration
st.set_page_config(
    page_title="Spice Business Intelligence Tool",
    page_icon="🌶️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3d59; /* Dark blue */
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    /* Sub-header for instructions */
    .sub-header {
        text-align: center;
        color: #555;
        margin-bottom: 2rem;
    }

    /* Styling for the detail cards */
    .detail-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transition: box-shadow 0.3s ease-in-out;
    }
    .detail-card:hover {
        box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    }
    .detail-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1e3d59;
        margin-bottom: 1rem;
    }

    /* Priority badges */
    .priority-high { color: #D32F2F; background-color: #FFCDD2; padding: 0.2rem 0.6rem; border-radius: 15px; font-weight: bold; }
    .priority-medium { color: #F57C00; background-color: #FFE0B2; padding: 0.2rem 0.6rem; border-radius: 15px; font-weight: bold; }
    .priority-low { color: #388E3C; background-color: #C8E6C9; padding: 0.2rem 0.6rem; border-radius: 15px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=600) # Cache data for 10 minutes
def load_all_data():
    """Load, combine, and professionally deduplicate all available business data."""
    data_dir = Path("data")
    data_frames = []
    
    # Use rglob to find all relevant CSVs recursively
    all_files = list(data_dir.rglob("*_businesses_*.csv"))
    
    if not all_files:
        return pd.DataFrame()

    for file in all_files:
        try:
            df = pd.read_csv(file)
            
            # Add lead type and standardize priority column
            if 'spice' in file.stem.lower():
                df['Lead Type'] = 'Spice'
                df.rename(columns={'Spice Priority': 'Priority'}, inplace=True)
            elif 'oil' in file.stem.lower():
                df['Lead Type'] = 'Cooking Oil'
                df.rename(columns={'Oil Priority': 'Priority'}, inplace=True)
            else:
                df['Lead Type'] = 'General'
                # Handle any other potential priority column names
                if 'Spice Priority' in df.columns:
                    df.rename(columns={'Spice Priority': 'Priority'}, inplace=True)
                elif 'Oil Priority' in df.columns:
                    df.rename(columns={'Oil Priority': 'Priority'}, inplace=True)
                elif 'Priority' not in df.columns:
                    df['Priority'] = 'LOW' # Default priority if none found
            
            # Infer borough from file path if not present
            if 'Borough' not in df.columns:
                if 'hackney' in str(file).lower():
                    df['Borough'] = 'Hackney'
                elif 'haringey' in str(file).lower():
                    df['Borough'] = 'Haringey'
                else:
                    df['Borough'] = 'Other'

            data_frames.append(df)
        except Exception as e:
            st.warning(f"Could not load {file.name}: {e}")

    if not data_frames:
        return pd.DataFrame()

    combined_df = pd.concat(data_frames, ignore_index=True)
    
    # --- Professional Deduplication Process ---
    # 1. Normalize text fields to create a stable key
    def normalize_key_text(text):
        return re.sub(r'[^a-z0-9]', '', str(text).lower())

    combined_df['normalized_name'] = combined_df['Business Name'].apply(normalize_key_text)
    
    # Use the first part of the address for a more stable address key
    combined_df['address_key'] = combined_df['Address'].str.split(',').str[0].apply(normalize_key_text)
    
    combined_df['dedupe_key'] = combined_df['normalized_name'] + '_' + combined_df['address_key']

    # 2. Score rows to keep the one with the most complete data
    combined_df['info_score'] = combined_df['Phone'].notna().astype(int) + \
                                combined_df['Website'].notna().astype(int) + \
                                (combined_df['Priority'] == 'HIGH').astype(int) # Prioritize high priority leads

    # Sort by the score (descending), so the best entry appears first for each group
    combined_df.sort_values('info_score', ascending=False, inplace=True)
    
    # 3. Drop duplicates, keeping the first (i.e., the highest-scored) entry
    initial_rows = len(combined_df)
    combined_df.drop_duplicates(subset=['dedupe_key'], keep='first', inplace=True)
    final_rows = len(combined_df)
    
    # Use a global flag to show the message only once
    if 'dedup_message_shown' not in st.session_state:
        st.sidebar.success(f"🔄 Removed {initial_rows - final_rows} duplicate entries.")
        st.session_state.dedup_message_shown = True

    # 4. Clean up temporary columns
    combined_df = combined_df.drop(columns=['normalized_name', 'address_key', 'dedupe_key', 'info_score'])
    
    # Final data preparation
    combined_df['Postcode'] = combined_df['Postcode'].str.split().str[0] # Use postcode district
    
    # Create a searchable string for the selectbox
    combined_df['SearchString'] = combined_df['Business Name'] + " (" + combined_df['Cuisine Type'].fillna('N/A') + ", " + combined_df['Postcode'].fillna('N/A') + ")"
    
    return combined_df.sort_values(by='Business Name').reset_index(drop=True)

def display_business_details(business_data):
    """Shows all details for a selected business in a professional card format."""
    st.markdown(f'<h2 class="detail-title">{business_data["Business Name"]}</h2>', unsafe_allow_html=True)

    # Priority badge
    priority = business_data.get("Priority", "LOW")
    st.markdown(f"**Priority:** <span class='priority-{priority.lower()}'>{priority.upper()}</span>", unsafe_allow_html=True)
    
    if priority == 'HIGH':
        st.info(f"🔥 **Top Prospect:** This business is a high-priority lead for **{business_data.get('Lead Type', 'products')}**.")
    elif priority == 'MEDIUM':
        st.info(f"💡 **Good Prospect:** This business is a potential customer.")

    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 📝 Business Information")
        st.markdown(f"**Cuisine:** `{business_data.get('Cuisine Type', 'N/A')}`")
        st.markdown(f"**Address:** `{business_data.get('Address', 'N/A')}`")
        st.markdown(f"**Postcode Area:** `{business_data.get('Postcode', 'N/A')}`")
        st.markdown(f"**Borough:** `{business_data.get('Borough', 'N/A')}`")

    with col2:
        st.markdown("#### 📞 Contact Details")
        st.markdown(f"**Phone:** `{business_data.get('Phone', 'Not Available')}`")
        st.markdown(f"**Website:** `{business_data.get('Website', 'Not Available')}`")
        st.markdown(f"**Data Source:** `{business_data.get('Source', 'N/A')}`")

    st.markdown("---")
    
    # Interactive Map for the specific business
    st.markdown("#### 📍 Location Map")
    lat = business_data.get('Latitude')
    lon = business_data.get('Longitude')

    if pd.notna(lat) and pd.notna(lon):
        map_center = [lat, lon]
        m = folium.Map(location=map_center, zoom_start=16)
        
        color_map = {'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}
        folium.Marker(
            location=map_center,
            popup=f"<b>{business_data['Business Name']}</b><br>{business_data['Address']}",
            tooltip=business_data['Business Name'],
            icon=folium.Icon(color=color_map.get(priority, 'blue'), icon='cutlery', prefix='fa')
        ).add_to(m)
        st_folium(m, width=700, height=400)
    else:
        st.warning("Location coordinates not available for this business.")

def display_filterable_data_table(data: pd.DataFrame):
    """Creates a filterable, searchable table of the entire dataset."""
    st.markdown("### 🗂️ Explore Full Business Dataset")
    st.markdown("Use the filters below to search the entire database. You can combine filters for a more powerful search.")

    # Create columns for filters
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        # Text search for Business Name or Cuisine
        search_text = st.text_input("Search by Name or Cuisine", placeholder="e.g., Tandoori, Pizza, Cafe")
    
    with filter_col2:
        # Multi-select for Lead Type
        lead_type_options = sorted(data['Lead Type'].unique().tolist())
        selected_lead_types = st.multiselect("Filter by Lead Type", options=lead_type_options, default=None)

    with filter_col3:
        # Multi-select for Borough
        borough_options = sorted(data['Borough'].unique().tolist())
        selected_boroughs = st.multiselect("Filter by Borough", options=borough_options, default=None)

    with filter_col4:
        # Multi-select for Priority
        priority_options = ['HIGH', 'MEDIUM', 'LOW']
        selected_priorities = st.multiselect("Filter by Priority", options=priority_options, default=None)
    
    # Apply filters
    filtered_df = data.copy()
    if search_text:
        # Filter by name or cuisine type
        filtered_df = filtered_df[
            filtered_df['Business Name'].str.contains(search_text, case=False, na=False) |
            filtered_df['Cuisine Type'].str.contains(search_text, case=False, na=False)
        ]
    
    if selected_boroughs:
        filtered_df = filtered_df[filtered_df['Borough'].isin(selected_boroughs)]
        
    if selected_priorities:
        filtered_df = filtered_df[filtered_df['Priority'].isin(selected_priorities)]

    if selected_lead_types:
        filtered_df = filtered_df[filtered_df['Lead Type'].isin(selected_lead_types)]
        
    st.markdown(f"**Showing `{len(filtered_df)}` of `{len(data)}` total businesses.**")
    
    # Display the dataframe with styled priorities for better visibility
    def get_row_style(row):
        style = ''
        priority = row['Priority']
        if priority == 'HIGH':
            style = 'background-color: #6d0000; color: white;' # Dark Red background, white text
        elif priority == 'MEDIUM':
            style = 'background-color: #7f3d00; color: white;' # Dark Orange background, white text
        elif priority == 'LOW':
            style = 'background-color: #004d00; color: white;' # Dark Green background, white text
        
        return [style] * len(row)

    st.dataframe(
        filtered_df[['Business Name', 'Lead Type', 'Priority', 'Cuisine Type', 'Address', 'Postcode', 'Borough', 'Phone', 'Website']].style.apply(get_row_style, axis=1), 
        use_container_width=True,
        height=500
    )

    # Add a download button for the filtered data
    if not filtered_df.empty:
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Filtered Data as CSV",
            data=csv,
            file_name="filtered_spice_businesses.csv",
            mime="text/csv",
        )

def main():
    # Header
    st.markdown('<h1 class="main-header">🌶️ Professional Business Lead Tool</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Search or drill-down to find your next B2B customer.</p>', unsafe_allow_html=True)

    # --- NEW: Priority Explanation Section ---
    with st.expander("💡 How are 'High Priority' leads calculated?"):
        st.markdown("""
        The priority is automatically assigned based on keywords in the business's name and cuisine type to identify the most valuable customers for each product.
        """)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🔥 Spice Leads")
            st.markdown("""
            - **High:** Businesses with cuisines that use a lot of spices.
              - *Keywords: `Indian`, `curry`, `tandoori`, `Chinese`, `Thai`, `Asian`*
            - **Medium:** General restaurants and takeaways.
              - *Keywords: `restaurant`, `kitchen`, `takeaway`*
            """)
        with col2:
            st.markdown("#### 🍳 Cooking Oil Leads")
            st.markdown("""
            - **High:** Businesses that do a lot of frying.
              - *Keywords: `fish and chips`, `fried chicken`, `kebab`, `fast food`*
            - **Medium:** General restaurants and cafes that use oil less intensively.
              - *Keywords: `restaurant`, `cafe`, `diner`, `grill`*
            """)

    # Load data
    data = load_all_data()

    if data.empty:
        st.error("⚠️ No data files found in the 'data' directory.")
        st.info("Please run the data extraction scripts (`hackney_spice_extractor.py`, `haringey_spice_extractor.py`) first.")
        return

    # --- 1. REAL-TIME SEARCH (PRIMARY INTERACTION) ---
    st.markdown("### 🔎 Search for a Business Directly")
    
    # Use a selectbox for a searchable dropdown experience
    business_list = [""] + data['SearchString'].tolist()
    
    selected_business_str = st.selectbox(
        label="Type to search for a business by name, cuisine, or postcode",
        options=business_list,
        index=0,
        help="Start typing and select a business to see its full details."
    )
    
    # --- 2. HIERARCHICAL DRILL-DOWN (SECONDARY INTERACTION) ---
    st.markdown("---")
    st.markdown("### 🗺️ Or, Explore by Area")

    # Keep track of selected business data
    selected_business_data = None
    
    # --- Drill-down columns ---
    col1, col2, col3 = st.columns(3)

    # a. Select Borough
    with col1:
        boroughs = [""] + sorted(data['Borough'].unique().tolist())
        selected_borough = st.selectbox("Step 1: Choose a Borough", options=boroughs)

    data_in_borough = data[data['Borough'] == selected_borough] if selected_borough else pd.DataFrame()

    # b. Select Postcode
    with col2:
        if not data_in_borough.empty:
            postcodes = [""] + sorted(data_in_borough['Postcode'].unique().tolist())
            selected_postcode = st.selectbox("Step 2: Choose a Postcode Area", options=postcodes)
            data_in_postcode = data_in_borough[data_in_borough['Postcode'] == selected_postcode] if selected_postcode else pd.DataFrame()
        else:
            st.selectbox("Step 2: Choose a Postcode Area", [], disabled=True)
            data_in_postcode = pd.DataFrame()

    # c. Select Business from drill-down
    with col3:
        if not data_in_postcode.empty:
            drilldown_business_list = [""] + data_in_postcode['SearchString'].tolist()
            selected_drilldown_business = st.selectbox("Step 3: Choose a Business", options=drilldown_business_list)
            if selected_drilldown_business:
                selected_business_str = selected_drilldown_business # This overrides search selection
        else:
            st.selectbox("Step 3: Choose a Business", [], disabled=True)

    st.markdown("---")

    # --- 3. DISPLAY SELECTED BUSINESS DETAILS ---
    if selected_business_str:
        # Find the full data for the selected business
        selected_business_data = data[data['SearchString'] == selected_business_str].iloc[0]
        
    if selected_business_data is not None:
        st.markdown('<div class="detail-card">', unsafe_allow_html=True)
        display_business_details(selected_business_data)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Select a business from the search bar or the drill-down menus to see its details here.")

    # --- 4. DISPLAY FULL, FILTERABLE DATA TABLE ---
    display_filterable_data_table(data)

if __name__ == "__main__":
    main() 