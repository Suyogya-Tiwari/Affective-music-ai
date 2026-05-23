import os
import numpy as np
import pickle
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
from network import create_network

def train_network(processed_dir="../data/processed", model_dir="."):
    """
    Loads the prepared data, builds the AI brain, and trains it!
    """
    # 1. Load the data we prepared in Session 2
    data_path = os.path.join(processed_dir, "network_data.npz")
    if not os.path.exists(data_path):
        print(f"Error: Could not find {data_path}. Did you run encode_sequences.py?")
        return
        
    print("Loading data...")
    data = np.load(data_path, allow_pickle=True)
    network_input_notes = data['input_notes']
    network_input_moods = data['input_moods']
    network_output = data['output']
    pitchnames = data['pitchnames']
    
    vocab_size = len(pitchnames)
    sequence_length = network_input_notes.shape[1]
    
    print(f"Data loaded! Vocab size: {vocab_size}, Sequence length: {sequence_length}")

    # Load emotion map to determine number of emotions
    emotion_map_path = os.path.join(processed_dir, "emotion_map.pkl")
    if os.path.exists(emotion_map_path):
        with open(emotion_map_path, 'rb') as f:
            emotion_map = pickle.load(f)
        num_emotions = len(emotion_map)
    else:
        num_emotions = 2
        print("WARNING: emotion_map.pkl not found, defaulting to 2 emotions.")

    # 2. Build the Neural Network
    print(f"Building the AI Architecture for {num_emotions} emotions...")
    model = create_network(sequence_length=sequence_length, vocab_size=vocab_size, num_emotions=num_emotions)
    
    # 3. Setup Training Rules (Callbacks)
    # We want to save the "weights" (the brain's memories) to a file named model.h5
    weight_path = os.path.join(model_dir, "model.h5")
    
    # ModelCheckpoint ensures we only save the weights when the AI actually improves
    checkpoint = ModelCheckpoint(
        weight_path, 
        monitor='loss', 
        verbose=1, 
        save_best_only=True, 
        mode='min'
    )
    
    # EarlyStopping stops training if the AI stops learning, saving us time
    early_stop = EarlyStopping(
        monitor='loss',
        patience=5, # Wait 5 epochs before giving up
        verbose=1
    )
    
    callbacks_list = [checkpoint, early_stop]
    
    # 4. Train the AI!
    print("Starting training... This might take a while depending on your CPU/GPU.")
    
    # We pass both inputs (Notes and Mood) as a list
    model.fit(
        [network_input_notes, network_input_moods], 
        network_output, 
        epochs=50,       # Number of times the AI loops through the entire dataset
        batch_size=64,   # How many sequences the AI looks at before updating its memory
        callbacks=callbacks_list
    )
    
    print(f"Training complete! Best weights saved to {weight_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    processed_dir = os.path.join(base_dir, "data", "processed")
    current_model_dir = os.path.dirname(os.path.abspath(__file__))
    
    train_network(processed_dir=processed_dir, model_dir=current_model_dir)
