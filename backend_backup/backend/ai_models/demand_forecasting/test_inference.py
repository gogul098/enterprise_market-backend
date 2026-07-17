import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def load_and_predict(model_path, mock_feature_data):
    """
    Loads a trained Random Forest model and predicts demand along with confidence bounds.
    """
    print(f"Loading model from {model_path}...")
    rf_model = joblib.load(model_path)
    
    # 1. Point Prediction
    predicted_demands = rf_model.predict(mock_feature_data)
    
    # 2. Confidence Intervals via Estimator Percentiles
    results = []
    
    for i in range(len(mock_feature_data)):
        # Extract features for a single prediction row
        row_features = mock_feature_data.iloc[[i]]
        
        # Get predictions from all individual trees in the forest
        tree_predictions = [tree.predict(row_features.values)[0] for tree in rf_model.estimators_]
        
        # Calculate 10th and 90th percentiles for this specific prediction
        lower_bound = np.percentile(tree_predictions, 10)
        upper_bound = np.percentile(tree_predictions, 90)
        
        results.append({
            'predicted_demand': int(round(predicted_demands[i])),
            'confidence_lower_bound': int(round(lower_bound)),
            'confidence_upper_bound': int(round(upper_bound))
        })
        
    return pd.DataFrame(results)

if __name__ == "__main__":
    # Simulate a scenario where a vendor wants to forecast demand for tomorrow
    target_date = datetime.today() + timedelta(days=1)
    
    print("Generating incoming mock data (as if queried from AWS today)...")
    # This is the exact 6-column schema the model expects
    mock_incoming_data = pd.DataFrame([
        {
            'day_of_week': target_date.weekday(),
            'is_weekend': 1 if target_date.weekday() >= 5 else 0,
            'lag_7': 45,               # The product sold 45 units last week
            'lag_1': 42,               # The product sold 42 units yesterday
            'sentiment_score': 0.85,   # Sentiment is currently very high!
            'rolling_sentiment_7d': 0.80
        },
        {
            'day_of_week': target_date.weekday(),
            'is_weekend': 1 if target_date.weekday() >= 5 else 0,
            'lag_7': 10,               # A poorly performing product
            'lag_1': 8,
            'sentiment_score': 0.20,   # Sentiment is very low
            'rolling_sentiment_7d': 0.25
        }
    ])
    
    # Run the inference
    # Note: Ensure the path points to where the joblib file was saved (root folder)
    model_file_path = "rf_demand_model.joblib"
    
    try:
        predictions_df = load_and_predict(model_file_path, mock_incoming_data)
        
        print("\nInference Results:")
        print("---------------------------------------------------------")
        # Combine inputs and outputs for clear display
        display_df = pd.concat([mock_incoming_data[['sentiment_score', 'lag_1']], predictions_df], axis=1)
        display_df.index = ['Product A (High Sentiment)', 'Product B (Low Sentiment)']
        print(display_df.to_string())
        print("---------------------------------------------------------")
        print("Test successful!")
        
    except FileNotFoundError:
        print(f"Error: Could not find the model file at {model_file_path}.")
        print("Run 'main.py' first from the root directory to generate the model file.")
