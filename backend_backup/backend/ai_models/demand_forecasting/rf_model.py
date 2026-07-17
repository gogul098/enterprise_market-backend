import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib

def engineer_features(df):
    """
    Adds time-series and lagging features to the dataset.
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['day_of_week'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
    
    # Create lag features (e.g., demand 7 days ago) per product
    df['lag_7'] = df.groupby('product_id')['daily_orders'].shift(7)
    df['lag_1'] = df.groupby('product_id')['daily_orders'].shift(1)
    
    # Rolling average of sentiment to capture trend
    df['rolling_sentiment_7d'] = df.groupby('product_id')['sentiment_score'].transform(lambda x: x.rolling(7, min_periods=1).mean())
    
    # Drop rows with NaN due to lags to create clean training set
    return df.dropna().reset_index(drop=True)

def train_and_forecast(df, forecast_horizon_days=7):
    """
    Trains a Random Forest and predicts future demand with confidence bounds.
    """
    df_features = engineer_features(df)
    
    features = ['day_of_week', 'is_weekend', 'lag_7', 'lag_1', 'sentiment_score', 'rolling_sentiment_7d']
    target = 'daily_orders'
    
    X = df_features[features]
    y = df_features[target]
    
    # Train the Random Forest Regressor
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X, y)
    
    # Save the trained model to disk
    model_path = "rf_demand_model.joblib"
    joblib.dump(rf, model_path)
    print(f"Model successfully saved to {model_path}")
    
    # Generate future mock data to predict on
    predictions = []
    
    # We will forecast for each product
    products = df_features['product_id'].unique()
    last_date = df_features['date'].max()
    
    for pid in products:
        product_df = df_features[df_features['product_id'] == pid].iloc[-1]
        
        # We recursively predict or just assume recent values persist for the horizon features
        current_lag_7 = product_df['lag_1'] # Simplification for mock forecast
        current_lag_1 = product_df['daily_orders']
        current_sentiment = product_df['rolling_sentiment_7d']
        
        for day in range(1, forecast_horizon_days + 1):
            target_date = last_date + pd.Timedelta(days=day)
            
            # Build inference feature vector
            x_infer = pd.DataFrame([{
                'day_of_week': target_date.dayofweek,
                'is_weekend': 1 if target_date.dayofweek >= 5 else 0,
                'lag_7': current_lag_7,
                'lag_1': current_lag_1,
                'sentiment_score': current_sentiment,
                'rolling_sentiment_7d': current_sentiment
            }])
            
            # 1. Point Prediction
            predicted_demand = rf.predict(x_infer)[0]
            
            # 2. Confidence Intervals via Estimator Percentiles
            # Extract predictions from all individual trees in the forest
            tree_predictions = [tree.predict(x_infer.values)[0] for tree in rf.estimators_]
            
            # Calculate 10th and 90th percentiles
            lower_bound = np.percentile(tree_predictions, 10)
            upper_bound = np.percentile(tree_predictions, 90)
            
            predictions.append({
                'product_id': pid,
                'warehouse_id': product_df['warehouse_id'],
                'target_date': target_date.date(),
                'predicted_demand': int(round(predicted_demand)),
                'confidence_lower_bound': int(round(lower_bound)),
                'confidence_upper_bound': int(round(upper_bound)),
                'driving_sentiment_score': round(current_sentiment, 2)
            })
            
            # Update rolling lags for next day's prediction (autoregressive step)
            current_lag_7 = current_lag_1
            current_lag_1 = predicted_demand
            
    return pd.DataFrame(predictions)
