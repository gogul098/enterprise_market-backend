import pandas as pd
import pymysql
from sshtunnel import SSHTunnelForwarder

def calculate_vendor_performance_score(df_vendor_reviews):
    """
    Calculates the vendor performance score based on:
    - Sentiment Score from our Multi-Modal Model (0.0 to 1.0)
    - Star Rating (1 to 5)
    - Helpful Votes (provides weight)
    - Product Quality (can be passed in df, assumed to be out of 5)
    
    Args:
    df_vendor_reviews (pd.DataFrame): DataFrame containing reviews for a single vendor.
        Must contain columns: 'sentiment_score', 'star_rating', 'helpful_votes'.
        Optionally 'product_quality'.
        
    Returns:
    float: Consolidated vendor performance score (0 to 100)
    """
    if len(df_vendor_reviews) == 0:
        return 0.0
        
    # Default product quality if not present
    if 'product_quality' not in df_vendor_reviews.columns:
        df_vendor_reviews['product_quality'] = 5.0 # Assume perfect if no data
        
    total_weight = 0
    total_score = 0
    
    for _, row in df_vendor_reviews.iterrows():
        # Cast to float to avoid Decimal * float exceptions
        s_score = float(row['sentiment_score'])
        s_rating = float(row['star_rating'])
        h_votes = float(row['helpful_votes'])
        p_quality = float(row['product_quality'])
        
        # Sentiment score (0-1) scaled to 0-100
        sentiment_val = s_score * 100
        
        # Star rating (1-5) scaled to 0-100
        stars_val = (s_rating / 5.0) * 100
        
        # Product quality (1-5) scaled to 0-100
        quality_val = (p_quality / 5.0) * 100
        
        # Weight based on helpfulness. Add 1 so every review has at least some weight.
        weight = 1.0 + h_votes
        
        # Average the three metrics for this specific review experience
        # You can adjust the weights of sentiment vs stars vs quality here
        review_consolidated_score = (sentiment_val * 0.4) + (stars_val * 0.3) + (quality_val * 0.3)
        
        total_score += (review_consolidated_score * weight)
        total_weight += weight
        
    if total_weight == 0:
        return 0.0
        
    final_vendor_score = total_score / total_weight
    return round(final_vendor_score, 2)

def update_vendor_score_in_db(vendor_id, score, pem_file_path="../LambdaFinancials.pem"):
    """
    Updates the vendor performance score in the AWS MySQL database robustly (direct or SSH).
    """
    ssh_host = '13.201.224.132'
    ssh_user = 'ubuntu'
    sql_user = 'marketplace_admin'
    sql_password = 'SuperSecretDBPassword123'
    db_name = 'rocks'
    
    connection = None
    tunnel = None
    try:
        # Try direct connection first
        connection = pymysql.connect(
            host=ssh_host,
            user=sql_user,
            password=sql_password,
            database=db_name,
            port=3306,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
    except Exception:
        try:
            # Fallback to SSH Tunnel
            tunnel = SSHTunnelForwarder(
                (ssh_host, 22),
                ssh_username=ssh_user,
                ssh_pkey=pem_file_path,
                remote_bind_address=('localhost', 3306)
            )
            tunnel.start()
            connection = pymysql.connect(
                host='127.0.0.1',
                user=sql_user,
                password=sql_password,
                database=db_name,
                port=tunnel.local_bind_port,
                cursorclass=pymysql.cursors.DictCursor
            )
        except Exception as e:
            print(f"Failed to connect to AWS Database: {e}")
            return
            
    try:
        with connection.cursor() as cursor:
            # Insert or Update the record (UPSERT)
            sql = """
            INSERT INTO vendor (vendor_id, performance_score) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE performance_score = %s
            """
            cursor.execute(sql, (vendor_id, score, score))
        connection.commit()
        print(f"Successfully updated Vendor #{vendor_id} with score {score} in AWS database.")
    except Exception as e:
        print(f"Failed to update database: {e}")
    finally:
        if connection:
            connection.close()
        if tunnel:
            tunnel.stop()
