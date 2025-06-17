#!/usr/bin/env python3
"""
Spice Business Intelligence Dashboard Launcher
Launch the professional dashboard for spice business data analysis
"""

import subprocess
import sys
import os
from pathlib import Path

def check_data_files():
    """Check if data files exist"""
    data_dir = Path("data")
    
    # Check for Hackney data
    hackney_files = list(data_dir.glob("hackney_spice_businesses_*.csv"))
    haringey_files = list(data_dir.rglob("haringey_spice_businesses_*.csv"))
    
    print("🔍 Checking for data files...")
    print(f"   Hackney data files: {len(hackney_files)} found")
    print(f"   Haringey data files: {len(haringey_files)} found")
    
    if not hackney_files and not haringey_files:
        print("\n⚠️  WARNING: No data files found!")
        print("   Please run one of these extraction scripts first:")
        print("   - python hackney_spice_extractor.py")
        print("   - python haringey_spice_extractor.py")
        return False
    
    total_businesses = 0
    if hackney_files:
        import pandas as pd
        latest_hackney = max(hackney_files, key=os.path.getctime)
        hackney_df = pd.read_csv(latest_hackney)
        total_businesses += len(hackney_df)
        print(f"   ✅ Hackney: {len(hackney_df)} businesses loaded")
    
    if haringey_files:
        import pandas as pd
        latest_haringey = max(haringey_files, key=os.path.getctime)
        haringey_df = pd.read_csv(latest_haringey)
        total_businesses += len(haringey_df)
        print(f"   ✅ Haringey: {len(haringey_df)} businesses loaded")
    
    print(f"\n📊 Total businesses available: {total_businesses}")
    return True

def main():
    print("🌶️  SPICE BUSINESS INTELLIGENCE DASHBOARD")
    print("=" * 50)
    
    # Check if data exists
    if not check_data_files():
        print("\n❌ Cannot launch dashboard without data.")
        return
    
    print("\n🚀 Launching dashboard...")
    print("📱 Dashboard will open in your default browser")
    print("🔗 Local URL: http://localhost:8501")
    print("\n💡 Tips:")
    print("   - Use Ctrl+C to stop the dashboard")
    print("   - Dashboard auto-refreshes when you save changes")
    print("   - Share the URL with your client for local viewing")
    
    print("\n" + "="*50)
    
    try:
        # Launch Streamlit dashboard
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "spice_business_dashboard.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"\n❌ Error launching dashboard: {e}")
        print("💡 Make sure Streamlit is installed: pip install streamlit")

if __name__ == "__main__":
    main() 