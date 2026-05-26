import os
import glob
import pickle
from music21 import converter, instrument, note, chord

def preprocess_midi_data(data_dir="../data/raw", save_dir="../data/processed"):
    """
    Reads all MIDI files from emotion-labeled subdirectories.
    Extracts notes/chords and maps the folder name to an emotion integer ID.
    Saves the parsed data for neural network training.
    """
    os.makedirs(save_dir, exist_ok=True)
    
    parsed_songs = []
    emotion_map = {}
    current_emotion_id = 0
    
    if not os.path.exists(data_dir):
        print(f"WARNING: Directory {data_dir} does not exist. Creating it.")
        os.makedirs(data_dir, exist_ok=True)
        print("Please place folders named after emotions (e.g., 'happy', 'sad') inside it with .mid files.")
        return

    subdirs = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
    
    if not subdirs:
        print(f"WARNING: No subdirectories found in {data_dir}.")
        return

    for emotion_name in subdirs:
        if emotion_name not in emotion_map:
            emotion_map[emotion_name] = current_emotion_id
            current_emotion_id += 1
            
        emotion_id = emotion_map[emotion_name]
        folder_path = os.path.join(data_dir, emotion_name)
        midi_files = glob.glob(os.path.join(folder_path, "*.mid"))
        
        print(f"Found {len(midi_files)} files for emotion: '{emotion_name}' (ID: {emotion_id})")
        
        for file in midi_files:
            print(f"Parsing {file}...")
            try:
                midi = converter.parse(file)
                notes = []
                parts = instrument.partitionByInstrument(midi)
                
                if parts:
                    notes_to_parse = parts.parts[0].recurse()
                else:
                    notes_to_parse = midi.flat.notes
                    
                for element in notes_to_parse:
                    if isinstance(element, note.Note):
                        notes.append(str(element.pitch))
                    elif isinstance(element, chord.Chord):
                        notes.append('.'.join(str(n) for n in element.normalOrder))
                        
                if len(notes) > 0:
                    parsed_songs.append({
                        "filename": os.path.basename(file),
                        "mood": emotion_id,
                        "notes": notes[:500]
                    })
                    
            except Exception as e:
                print(f"Error parsing {file}: {e}")
                
    with open(os.path.join(save_dir, "parsed_songs.pkl"), 'wb') as filepath:
        pickle.dump(parsed_songs, filepath)
        
    with open(os.path.join(save_dir, "emotion_map.pkl"), 'wb') as filepath:
        pickle.dump(emotion_map, filepath)
        
    print(f"\nSuccessfully processed {len(parsed_songs)} songs across {len(emotion_map)} emotions!")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(base_dir, "data", "raw")
    processed_dir = os.path.join(base_dir, "data", "processed")
    preprocess_midi_data(data_dir=raw_dir, save_dir=processed_dir)
