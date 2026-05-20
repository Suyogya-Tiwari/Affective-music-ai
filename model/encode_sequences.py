import pickle
import numpy as np
import os
from tensorflow.keras.utils import to_categorical

def encode_sequences(processed_dir="../data/processed", sequence_length=100):
    """
    Takes the parsed string notes and converts them into numerical tensors
    ready for the Keras LSTM model.
    """
    # Load the parsed songs we created yesterday
    data_path = os.path.join(processed_dir, "parsed_songs.pkl")
    if not os.path.exists(data_path):
        print(f"Error: Could not find {data_path}. Run preprocess.py first.")
        return
        
    with open(data_path, 'rb') as filepath:
        parsed_songs = pickle.load(filepath)
        
    # 1. Get all unique pitches/chords to build the vocabulary
    all_notes = []
    for song in parsed_songs:
        all_notes.extend(song["notes"])
        
    pitchnames = sorted(set(all_notes))
    vocab_size = len(pitchnames)
    
    print(f"Total notes processed: {len(all_notes)}")
    print(f"Unique vocabulary size: {vocab_size}")
    
    # Create a mapping dictionary from note string to integer (e.g., 'C4' -> 12)
    note_to_int = dict((note, number) for number, note in enumerate(pitchnames))
    
    network_input_notes = []
    network_input_moods = []
    network_output = []
    
    # 2. Create the sequences
    for song in parsed_songs:
        notes = song["notes"]
        mood = song["mood"]
        
        # We need at least 'sequence_length' notes in a song to create a training sequence
        if len(notes) <= sequence_length:
            continue
            
        # Slide a window of 'sequence_length' over the notes
        for i in range(0, len(notes) - sequence_length):
            sequence_in = notes[i:i + sequence_length]
            sequence_out = notes[i + sequence_length]
            
            # Convert string notes to integers using our dictionary
            network_input_notes.append([note_to_int[char] for char in sequence_in])
            network_input_moods.append(mood)
            network_output.append(note_to_int[sequence_out])
            
    n_patterns = len(network_input_notes)
    print(f"Total sequences created: {n_patterns}")
    
    if n_patterns == 0:
        print("No sequences created. Make sure your MIDI files are long enough!")
        return

    # 3. Format inputs for the LSTM network (samples, time steps, features)
    network_input_notes = np.reshape(network_input_notes, (n_patterns, sequence_length, 1))
    
    # Normalize notes so the values are between 0 and 1 (helps the neural network learn faster)
    network_input_notes = network_input_notes / float(vocab_size)
    
    # Format moods as a numpy array
    network_input_moods = np.array(network_input_moods)
    
    # One-hot encode the output (e.g., 3 becomes [0, 0, 0, 1, 0, ...])
    network_output = to_categorical(network_output, num_classes=vocab_size)
    
    # Save everything into a compressed numpy zip file (.npz)
    save_path = os.path.join(processed_dir, "network_data.npz")
    np.savez(
        save_path, 
        input_notes=network_input_notes, 
        input_moods=network_input_moods, 
        output=network_output,
        pitchnames=pitchnames # We MUST save this so we can convert numbers back to notes later!
    )
    
    print(f"Network data saved to {save_path}")

if __name__ == "__main__":
    print("Starting Sequence Encoding Pipeline...")
    
    # We use paths relative to this script's location
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    processed_dir = os.path.join(base_dir, "data", "processed")
    
    encode_sequences(processed_dir=processed_dir)
