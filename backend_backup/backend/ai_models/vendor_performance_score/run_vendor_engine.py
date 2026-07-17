import os
import pandas as pd
import pymysql
from sshtunnel import SSHTunnelForwarder
from vendor_scoring import calculate_vendor_performance_score, update_vendor_score_in_db

def run_engine():
    print("Starting Vendor Performance Scoring Engine...")
    
    ssh_host = '13.201.224.132'
    ssh_user = 'ubuntu'
    sql_user = 'marketplace_admin'
    sql_password = 'SuperSecretDBPassword123'
    db_name = 'rocks'
    # Resolve PEM file relative to this script's directory (the parent 'rocks' folder)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pem_file = os.path.join(base_dir, '..', 'LambdaFinancials.pem')
    
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
        print("Connected directly to AWS MySQL for read-fetch!")
    except Exception as e:
        try:
            # Fallback to SSH Tunnel
            tunnel = SSHTunnelForwarder(
                (ssh_host, 22),
                ssh_username=ssh_user,
                ssh_pkey=pem_file,
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
            print("Connected to AWS MySQL via SSH Tunnel for read-fetch!")
        except Exception as tunnel_e:
            print(f"Failed to connect to database. {tunnel_e}")
            return

    try:
        # Fetch the scored reviews joined with the products table to map to vendors
        with connection.cursor() as cursor:
            sql = """
            SELECT 
                p.vendor_id, 
                r.ai_sentiment_score as sentiment_score, 
                r.star_rating, 
                r.helpful_votes 
            FROM product_reviews r
            JOIN products p ON r.product_id = p.product_id
            WHERE r.ai_sentiment_score IS NOT NULL
            """
            cursor.execute(sql)
            results = cursor.fetchall()
            
        if not results:
            print("No scored reviews found in the database. Run sentiment analysis first.")
            return
            
        df = pd.DataFrame(results)
        print(f"Fetched {len(df)} scored reviews across {df['vendor_id'].nunique()} unique vendors.")
        
        # We don't need the read connection anymore
        connection.close()
        connection = None
        if tunnel:
            tunnel.stop()
            tunnel = None
            
        # Group by vendor and calculate scores
        for vendor_id, df_vendor in df.groupby('vendor_id'):
            print(f"\nProcessing Vendor #{vendor_id}...")
            
            # The calculate_vendor_performance_score assumes 5.0 product quality if not provided,
            # which perfectly isolates the review impact!
            final_score = calculate_vendor_performance_score(df_vendor)
            print(f"Calculated Score for Vendor #{vendor_id}: {final_score}")
            
            # Push to the database using the module function
            # This opens its own connection per the design in vendor_scoring.py
            update_vendor_score_in_db(vendor_id, final_score, pem_file_path=pem_file)
            
        print("\nVendor Performance Scoring complete! The AWS `vendor` table is fully updated.")

    except Exception as e:
        print(f"Data processing failed: {e}")
    finally:
        if connection:
            connection.close()
        if tunnel:
            tunnel.stop()

if __name__ == "__main__":
    run_engine()
