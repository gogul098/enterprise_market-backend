import time
from backend.celery_app import celery_app
from backend.cache import set_cache

@celery_app.task(name="vendor_sentiment_analysis")
def analyze_vendor_sentiment(vendor_id: str):
    """
    Mock Celery Task for processing AI sentiment analysis on a Vendor's reviews.
    This demonstrates offloading a heavy task to a background worker.
    """
    print(f"[Celery] Starting sentiment analysis for vendor {vendor_id}...")
    
    # Simulate heavy machine learning processing
    time.sleep(5)
    
    # Simulated result
    result = {
        "vendor_id": vendor_id,
        "sentiment_score": 0.87,
        "classification": "Highly Positive",
        "processed_reviews": 142
    }
    
    print(f"[Celery] Completed sentiment analysis for vendor {vendor_id}: {result}")
    
    # Cache the result in Redis for immediate retrieval by the frontend
    cache_key = f"sentiment_analysis:{vendor_id}"
    set_cache(cache_key, result, ex=3600)  # Cache for 1 hour
    
    return result
