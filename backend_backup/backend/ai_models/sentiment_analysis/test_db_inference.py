import os
import torch
import joblib
import pandas as pd
import pymysql
from sshtunnel import SSHTunnelForwarder

# Import the model architecture and preprocessing logic
from model import MultiModalMarketplaceModel
from data_preprocessing import preprocess_data

def process_and_update_reviews(pem_file_path="../LambdaFinancials.pem"):
    """
    Connects to the AWS database, fetches reviews missing a sentiment score,
    runs the PyTorch model on them, and updates the database with the predictions.
    """
    ssh_host = '13.201.224.132'
    ssh_user = 'ubuntu'
    sql_host = '127.0.0.1'
    sql_user = 'marketplace_admin'
    sql_password = 'SuperSecretDBPassword123'
    db_name = 'rocks'

    # Load Model and Vocab
    model_dir = 'saved_models'
    model_path = os.path.join(model_dir, 'multimodal_sentiment_v1.pt')
    vocab_path = os.path.join(model_dir, 'vocab.joblib')

    if not os.path.exists(model_path) or not os.path.exists(vocab_path):
        print(f"Error: Model or vocab not found in {model_dir}/. Run main.py first to train and save them.")
        return

    print("Loading vocabulary and initializing model...")
    vocab = joblib.load(vocab_path)
    vocab_size = len(vocab)
    
    # Initialize the same architecture as training
    model = MultiModalMarketplaceModel(
        vocab_size=vocab_size,
        embed_dim=50,
        hidden_dim=64,
        meta_dim=4,
        output_dim=1,
        n_layers=1,
        drop_prob=0.3
    )
    
    # Load the trained weights
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device)
    print(f"Model loaded successfully on {device}.")

    # Connect to AWS Database
    print("Attempting to connect to AWS database...")
    connection = None
    try:
        # Try direct connection first (if port 3306 is open)
        connection = pymysql.connect(
            host=ssh_host,
            user=sql_user,
            password=sql_password,
            database=db_name,
            port=3306,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        print("Connected directly to AWS MySQL!")
    except Exception as direct_e:
        print(f"Direct connection failed, trying SSH Tunnel... ({direct_e})")
        try:
            # Fallback to SSH Tunnel
            tunnel = SSHTunnelForwarder(
                (ssh_host, 22),
                ssh_username=ssh_user,
                ssh_pkey=pem_file_path,
                remote_bind_address=('localhost', 3306) # Use localhost instead of 127.0.0.1 for strict MySQL permissions
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
            print("Connected to AWS MySQL via SSH Tunnel!")
        except Exception as ssh_e:
            print(f"AWS Database operation completely failed. Tunnel Error: {ssh_e}")
            return
            
    try:
        # Fetch un-scored reviews
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT review_id, review_body, star_rating, verified_purchase, helpful_votes, total_votes 
                FROM product_reviews 
                WHERE ai_sentiment_score IS NULL 
                LIMIT 5
            """)
            reviews = cursor.fetchall()
            
        if not reviews:
            print("No reviews found in the database that need a sentiment score.")
            print("Please insert the mock SQL records first.")
            return
            
        print(f"Fetched {len(reviews)} unscored reviews from AWS.")
        df = pd.DataFrame(reviews)
        
        # Preprocess the fetched data
        print("Preprocessing data for inference...")
        texts = df['review_body'].astype(str).fillna("").values
        
        from data_preprocessing import tokenize_and_pad, clean_and_scale_metadata
        texts_seq = tokenize_and_pad(texts, vocab, max_len=50)
        meta_seq = clean_and_scale_metadata(df)
        
        # Run Inference
        print("Running PyTorch model inference...")
        predictions = []
        with torch.no_grad():
            for i in range(len(df)):
                t = torch.tensor([texts_seq[i]], dtype=torch.long).to(device)
                m = torch.tensor([meta_seq[i]], dtype=torch.float32).to(device)
                out, _ = model(t, m)
                predictions.append((round(out.item(), 2), df.iloc[i]['review_id']))
                
        # Update Database
        print("Pushing calculated sentiment scores back to AWS...")
        with connection.cursor() as cursor:
            update_sql = "UPDATE product_reviews SET ai_sentiment_score = %s WHERE review_id = %s"
            cursor.executemany(update_sql, predictions)
        connection.commit()
        
        print("\nDatabase Update Successful!")
        for score, r_id in predictions:
            print(f"Review #{r_id} updated with sentiment score: {score}")

    except Exception as e:
        print(f"Data processing failed: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    process_and_update_reviews()
