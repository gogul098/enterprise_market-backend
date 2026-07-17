import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_mock_historical_data(days=90, num_products=5, base_warehouse_id=1):
    """
    Generates mock daily order volumes for multiple products.
    Injects a 'sentiment_score' that positively correlates with demand 
    to make the data self-explanatory for vendors (high sentiment = high demand).
    """
    np.random.seed(42)
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    data = []
    
    for product_id in range(1, num_products + 1):
        # Base demand and sentiment profile for the product
        base_demand = np.random.randint(10, 50)
        # Sentiment score between 0 and 1
        base_sentiment = np.random.uniform(0.4, 0.9)
        
        for dt in date_range:
            # Add some daily noise to sentiment
            daily_sentiment = np.clip(np.random.normal(base_sentiment, 0.05), 0, 1)
            
            # Demand is base_demand + a strong multiplier based on sentiment + weekend spikes + noise
            is_weekend = 1 if dt.weekday() >= 5 else 0
            sentiment_boost = daily_sentiment * 30  # High sentiment pushes demand up significantly
            weekend_boost = is_weekend * 15
            noise = np.random.randint(-5, 10)
            
            daily_demand = max(0, int(base_demand + sentiment_boost + weekend_boost + noise))
            
            data.append({
                'date': dt.date(),
                'product_id': product_id,
                'warehouse_id': base_warehouse_id,
                'sentiment_score': round(daily_sentiment, 2),
                'daily_orders': daily_demand
            })
            
    df = pd.DataFrame(data)
    # Sort for time-series integrity
    df = df.sort_values(by=['product_id', 'date']).reset_index(drop=True)
    return df
