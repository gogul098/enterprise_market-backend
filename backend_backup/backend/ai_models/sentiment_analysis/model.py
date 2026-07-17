import torch
import torch.nn as nn
import torch.nn.functional as F

class MultiModalMarketplaceModel(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, meta_dim=4, output_dim=1, n_layers=2, drop_prob=0.5):
        super().__init__()
        
        # ==========================================
        # HEAD A: The Text Sequence (LSTM)
        # ==========================================
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, n_layers, dropout=drop_prob, batch_first=True)
        
        # ==========================================
        # HEAD B: The Metadata Network (Dense Layers)
        # ==========================================
        # meta_dim is 4 (verified, log_helpful, log_total, ratio)
        self.meta_fc1 = nn.Linear(meta_dim, 16)
        self.meta_fc2 = nn.Linear(16, 8)
        
        # ==========================================
        # THE MERGE LAYER
        # ==========================================
        # Combine the hidden_dim from LSTM + the 8 features from Metadata
        combined_dim = hidden_dim + 8
        self.fc_final = nn.Linear(combined_dim, output_dim)
        self.sigmoid = nn.Sigmoid()
        self.dropout = nn.Dropout(drop_prob)

    def forward(self, text, meta, hidden=None):
        # 1. Process Text through LSTM
        embeds = self.embedding(text)
        
        if hidden is None:
            lstm_out, hidden = self.lstm(embeds)
        else:
            lstm_out, hidden = self.lstm(embeds, hidden)
            
        text_features = lstm_out[:, -1, :] # Extract the final time-step state
        
        # 2. Process Metadata through Dense Layers
        meta_features = F.relu(self.meta_fc1(meta))
        meta_features = F.relu(self.meta_fc2(meta_features))
        
        # 3. Concatenate Text and Metadata tensors horizontally
        # text_features shape: [batch_size, hidden_dim]
        # meta_features shape: [batch_size, 8]
        combined = torch.cat((text_features, meta_features), dim=1)
        
        # 4. Final Classification
        out = self.dropout(combined)
        out = self.fc_final(out)
        final_score = self.sigmoid(out)
        
        return final_score, hidden

def init_hidden(self, batch_size, device="cpu"):
    # Optional helper to initialize hidden state if not handling it implicitly
    weight = next(self.parameters()).data
    hidden = (weight.new(self.lstm.num_layers, batch_size, self.lstm.hidden_size).zero_().to(device),
              weight.new(self.lstm.num_layers, batch_size, self.lstm.hidden_size).zero_().to(device))
    return hidden
