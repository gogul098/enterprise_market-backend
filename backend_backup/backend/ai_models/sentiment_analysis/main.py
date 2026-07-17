import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import sys
import os

from data_preprocessing import get_dataloaders
from model import MultiModalMarketplaceModel

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vendor_performance_score')))
from vendor_scoring import calculate_vendor_performance_score

import random

def generate_dummy_data(n=20000):
    """Generates a large, varied dummy dataset for robust emotion/sentiment training."""
    print(f"Generating large dataset of {n} records...")
    
    # Emotional variations
    positive_reviews = [
        "This product is absolutely amazing. Highly recommended!",
        "Loved it! Best purchase of the year.",
        "Incredible quality, it completely exceeded my expectations.",
        "Very happy with this. Will buy again.",
        "Fantastic design and feels very premium."
    ]
    negative_reviews = [
        "Terrible experience. The item broke on the first day.",
        "I hated it. Complete waste of money.",
        "Extremely disappointed. Do not buy this.",
        "Awful customer service and defective product.",
        "Worst thing I have ever bought online."
    ]
    neutral_reviews = [
        "It is okay, gets the job done but could be better.",
        "Average product, nothing special.",
        "It works, but it's a bit too expensive for what it is.",
        "Not bad, but not great either."
    ]
    
    data = []
    for i in range(n):
        # Decide emotion label randomly
        sentiment_type = np.random.choice(['positive', 'negative', 'neutral'], p=[0.5, 0.3, 0.2])
        
        if sentiment_type == 'positive':
            review_text = random.choice(positive_reviews)
            headline = random.choice(["Great!", "Awesome", "Love it", "Fantastic"])
            star = np.random.choice([4, 5])
            helpful = np.random.randint(50, 100) # High correlation for positive
        elif sentiment_type == 'negative':
            review_text = random.choice(negative_reviews)
            headline = random.choice(["Terrible!", "Awful", "Hate it", "Trash"])
            star = np.random.choice([1, 2])
            helpful = np.random.randint(0, 20)   # Low correlation for negative
        else:
            review_text = random.choice(neutral_reviews)
            headline = random.choice(["Okay", "Average", "Meh"])
            star = 3
            helpful = np.random.randint(20, 50)  # Mid correlation for neutral
        total = helpful + np.random.randint(0, 50)
            
        data.append({
            'marketplace': 'US',
            'customer_id': f'C{i}',
            'review_id': f'R{i}',
            'product_id': f'P{i % 10}',
            'product_parent': f'PP{i % 10}',
            'product_title': f'Product {i % 10}',
            'product_category': 'Electronics',
            'star_rating': star,
            'helpful_votes': helpful,
            'total_votes': total,
            'vine': 'N',
            'verified_purchase': np.random.choice(['Y', 'N']),
            'review_headline': headline,
            'review_body': review_text,
            'review_date': '2023-01-01'
        })
        
    return pd.DataFrame(data)

def train_model(model, train_loader, val_loader, epochs=100, lr=0.001, device='cuda'):
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # Ensure device string is valid for PyTorch ('cuda', not 'gpu')
    if device == 'gpu':
        device = 'cuda'
        
    model.to(device)
    
    print("Starting training...")
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        
        for texts, meta, labels in train_loader:
            texts, meta, labels = texts.to(device), meta.to(device), labels.to(device)
            
            # THE FIX: Reshape labels to match outputs [batch_size, 1]
            labels = labels.view(-1, 1).float()
            
            optimizer.zero_grad()
            outputs, _ = model(texts, meta)
            loss = criterion(outputs, labels)
            
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            
        # Validation
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for texts, meta, labels in val_loader:
                texts, meta, labels = texts.to(device), meta.to(device), labels.to(device)
                
                # THE FIX: Reshape labels for validation as well
                labels = labels.view(-1, 1).float()
                
                outputs, _ = model(texts, meta)
                
                loss = criterion(outputs, labels)
                val_loss += loss.item()
                
                predicted = (outputs >= 0.5).float()
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
                
        print(f"Epoch {epoch+1}/{epochs} - "
              f"Train Loss: {train_loss/len(train_loader):.4f} - "
              f"Val Loss: {val_loss/len(val_loader):.4f} - "
              f"Val Acc: {100 * correct / total:.2f}%")
              
    return model

def main():
    # 1. Load Data (Using dummy data here for testing)
    print("Loading data...")
    # NOTE: Replace generate_dummy_data() with pd.read_csv('your_dataset.csv')
    df = generate_dummy_data(20000)
    
    # 2. Preprocess Data
    batch_size = 64
    train_loader, val_loader, vocab = get_dataloaders(df, batch_size=batch_size, max_words=5000, max_len=50)
    
    # 3. Initialize Model
    vocab_size = len(vocab)
    embed_dim = 50
    hidden_dim = 64
    
    model = MultiModalMarketplaceModel(
        vocab_size=vocab_size,
        embed_dim=embed_dim,
        hidden_dim=hidden_dim,
        meta_dim=4,       # verified, log_helpful, log_total, ratio
        output_dim=1,     # binary sentiment
        n_layers=1,
        drop_prob=0.3
    )
    
    # 4. Train Model
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Training on {device} with 100 epochs...")
    trained_model = train_model(model, train_loader, val_loader, epochs=100, device=device)
    
    # 5. Vendor Scoring Simulation
    print("\n--- Simulating Vendor Scoring ---")
    # Take a small sample to represent a specific vendor's product reviews
    vendor_df = df.head(10).copy()
    vendor_df['product_quality'] = [5.0, 3.0, 4.0, 2.0, 5.0, 1.0, 4.0, 5.0, 3.0, 4.0]
    
    # Get model sentiment scores for these reviews
    # In a real scenario, you'd process these through the model pipeline
    # Here we just randomly mock the output for demonstration, or run it through the trained model:
    
    trained_model.eval()
    sentiment_scores = []
    
    # Need to run data preprocessing for the sample
    # Re-using the get_dataloaders preprocessing logic for simplicity in inference
    from data_preprocessing import preprocess_data
    texts_seq, meta_seq, _, _ = preprocess_data(vendor_df, max_words=5000, max_len=50) # using same max params
    
    with torch.no_grad():
        for i in range(len(vendor_df)):
            t = torch.tensor([texts_seq[i]], dtype=torch.long).to(device)
            m = torch.tensor([meta_seq[i]], dtype=torch.float32).to(device)
            out, _ = trained_model(t, m)
            sentiment_scores.append(out.item())
            
    vendor_df['sentiment_score'] = sentiment_scores
    
    # Calculate performance score
    score = calculate_vendor_performance_score(vendor_df)
    
    print("\nVendor Review Sample:")
    print(vendor_df[['review_headline', 'star_rating', 'sentiment_score', 'helpful_votes']].head())
    print(f"\nConsolidated Vendor Performance Score (0-100): {score}")
    print("---------------------------------")
    
    # 6. Save the trained model weights and vocab
    import os
    import joblib
    MODEL_DIR = 'saved_models'
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    model_path = os.path.join(MODEL_DIR, 'multimodal_sentiment_v1.pt')
    vocab_path = os.path.join(MODEL_DIR, 'vocab.joblib')
    
    torch.save(trained_model.state_dict(), model_path)
    joblib.dump(vocab, vocab_path)
    
    print(f"\nModel weights saved to {model_path}")
    print(f"Vocabulary saved to {vocab_path}")
    print("Pipeline ready! Replace dummy data generation with your downloaded dataset loading logic.")
    return trained_model, vocab

if __name__ == "__main__":
    trained_model, vocab = main()