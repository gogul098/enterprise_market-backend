import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import torch
from torch.utils.data import Dataset, DataLoader
from collections import Counter

class AmazonReviewDataset(Dataset):
    def __init__(self, texts, metadata, labels):
        self.texts = torch.tensor(texts, dtype=torch.long)
        self.metadata = torch.tensor(metadata, dtype=torch.float32)
        self.labels = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)
        
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        return self.texts[idx], self.metadata[idx], self.labels[idx]

def clean_and_scale_metadata(df):
    """
    Cleans and scales metadata according to the specified rules.
    Expects df to have columns: 'verified_purchase', 'helpful_votes', 'total_votes'
    """
    # 1. Verified Purchase (Binary: True=1.0, False=0.0)
    # The dataset typically has 'Y'/'N' for verified_purchase
    if df['verified_purchase'].dtype == bool:
        verified_binary = df['verified_purchase'].astype(float).values
    else:
        verified_binary = (df['verified_purchase'].astype(str).str.upper() == 'Y').astype(float).values
    
    # Fill NAs for votes just in case
    helpful_votes = pd.to_numeric(df['helpful_votes'], errors='coerce').fillna(0).values
    total_votes = pd.to_numeric(df['total_votes'], errors='coerce').fillna(0).values

    # 2. Helpful Votes & Total Votes (Logarithmic Transformation)
    log_helpful = np.log1p(helpful_votes)
    log_total = np.log1p(total_votes)
    
    # 3. Helpfulness Ratio
    # Handle division by zero
    helpful_ratio = np.where(
        total_votes > 0,
        helpful_votes / total_votes,
        0.0
    )
    
    metadata = np.stack([verified_binary, log_helpful, log_total, helpful_ratio], axis=1)
    return metadata

def build_vocab(texts, max_words=10000):
    all_words = ' '.join(texts).lower().split()
    counts = Counter(all_words)
    vocab = {word: i + 2 for i, (word, _) in enumerate(counts.most_common(max_words - 2))}
    vocab['<PAD>'] = 0
    vocab['<UNK>'] = 1
    return vocab

def tokenize_and_pad(texts, vocab, max_len=100):
    encoded = []
    for text in texts:
        tokens = [vocab.get(word, 1) for word in text.lower().split()]
        if len(tokens) < max_len:
            tokens = tokens + [0] * (max_len - len(tokens))
        else:
            tokens = tokens[:max_len]
        encoded.append(tokens)
    return np.array(encoded)

def preprocess_data(df, max_words=10000, max_len=100):
    """
    Main preprocessing pipeline.
    Expects df with columns: 'review_body', 'star_rating', 'verified_purchase', 'helpful_votes', 'total_votes'
    """
    # Clean up star_rating and create binary target (e.g., >= 4 is positive)
    stars = pd.to_numeric(df['star_rating'], errors='coerce').fillna(3)
    labels = (stars >= 4).astype(int).values
    
    # Process metadata
    metadata = clean_and_scale_metadata(df)
    
    # Process text (using review_body)
    texts = df['review_body'].astype(str).fillna("").values
    vocab = build_vocab(texts, max_words)
    text_sequences = tokenize_and_pad(texts, vocab, max_len)
    
    return text_sequences, metadata, labels, vocab

def get_dataloaders(df, batch_size=32, test_size=0.2, max_words=10000, max_len=100):
    texts, metadata, labels, vocab = preprocess_data(df, max_words, max_len)
    
    # Train-test split
    X_text_train, X_text_val, X_meta_train, X_meta_val, y_train, y_val = train_test_split(
        texts, metadata, labels, test_size=test_size, random_state=42
    )
    
    train_dataset = AmazonReviewDataset(X_text_train, X_meta_train, y_train)
    val_dataset = AmazonReviewDataset(X_text_val, X_meta_val, y_val)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    return train_loader, val_loader, vocab
