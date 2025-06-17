from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import logging
import os
from dotenv import load_dotenv
from pathlib import Path

from data_loader import load_and_clean_data

# Load environment variables from root directory
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Evergreen Business Leads API",
    description="Provides access to cleaned and deduplicated business leads.",
    version="1.0.0",
)

# CORS (Cross-Origin Resource Sharing) - get from environment
allowed_origins_str = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173')
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]

# Add production URLs if in production
if os.getenv('ENVIRONMENT') == 'production':
    production_frontend = os.getenv('PRODUCTION_FRONTEND_URL')
    if production_frontend:
        allowed_origins.append(production_frontend)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

business_data_cache: List[Dict[str, Any]] = []

@app.on_event("startup")
def startup_event():
    """
    Load data on startup and cache it.
    This makes subsequent requests much faster.
    """
    logger.info("Application startup: Loading and cleaning data...")
    try:
        global business_data_cache
        business_data_cache = load_and_clean_data()
        if not business_data_cache:
            logger.warning("No data loaded. The 'data' directory might be empty or CSV files are missing.")
        else:
            logger.info(f"Successfully loaded and cached {len(business_data_cache)} business records.")
    except Exception as e:
        logger.error(f"Fatal error during data loading: {e}", exc_info=True)
        # In a real-world scenario, you might want the app to fail startup
        # if data is essential. For now, we'll let it start empty.
        business_data_cache = []

@app.get("/api/businesses",
         response_model=List[Dict[str, Any]],
         summary="Get All Business Leads",
         description="Returns a list of all business leads after cleaning and deduplication.",
         tags=["Businesses"])
def get_businesses():
    """
    Main endpoint to retrieve all processed business data.
    """
    if not business_data_cache:
        raise HTTPException(
            status_code=404, 
            detail="No business data available. The server may have failed to load the data source."
        )
    return business_data_cache

@app.get("/api/reload",
         summary="Reload Business Data",
         description="Reloads business data from CSV files (useful after data extraction).",
         tags=["Admin"])
def reload_data():
    """
    Reload data from files - useful when new data has been extracted.
    """
    try:
        global business_data_cache
        business_data_cache = load_and_clean_data()
        return {
            "status": "success",
            "message": f"Reloaded {len(business_data_cache)} business records",
            "count": len(business_data_cache)
        }
    except Exception as e:
        logger.error(f"Error reloading data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reload data: {str(e)}")

@app.get("/api/health",
         summary="Health Check",
         description="Simple health check endpoint to confirm the API is running.",
         tags=["Status"])
def health_check():
    return {
        "status": "ok",
        "environment": os.getenv('ENVIRONMENT', 'development'),
        "data_loaded": len(business_data_cache) > 0,
        "business_count": len(business_data_cache),
        "allowed_origins": allowed_origins
    } 