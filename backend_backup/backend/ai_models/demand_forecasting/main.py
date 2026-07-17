import pandas as pd
from dummy_data import generate_mock_historical_data
from rf_model import train_and_forecast
from db_updater import push_forecasts_to_db

def main():
    print("1. Generating mock historical order and sentiment data...")
    # Generates 90 days of daily data for 5 products, incorporating sentiment scores
    df_history = generate_mock_historical_data(days=90, num_products=5)
    
    print("\nSample Historical Data (Notice the correlation between Sentiment and Orders):")
    print(df_history[['date', 'product_id', 'sentiment_score', 'daily_orders']].tail(5))
    
    print("\n2. Training Random Forest Model & Engineering Time-Series Features...")
    # Trains RF on lags and rolling sentiment, outputs forecast with confidence percentiles
    forecast_df = train_and_forecast(df_history, forecast_horizon_days=7)
    
    print("\n3. Forecast Generated (Self-Explanatory Data for Vendors):")
    print("---------------------------------------------------------")
    print(forecast_df[['product_id', 'target_date', 'driving_sentiment_score', 
                       'predicted_demand', 'confidence_lower_bound', 'confidence_upper_bound']].head(10))
    print("---------------------------------------------------------")
    
    print("\n4. Pushing forecasts to AWS Database (demand_forecasts table)...")
    # Warning: Ensure the LambdaFinancials.pem is located in the root rocks folder
    # push_forecasts_to_db(forecast_df, pem_file_path="../LambdaFinancials.pem")
    print("Simulated database push completed (uncomment push_forecasts_to_db to execute).")

if __name__ == "__main__":
    main()
