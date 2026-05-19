import os
import glob
import pickle
from music21 import converter, instrument, note, chord

def preprocess_midi_data(data_dir="../data/raw_midi", save_dir="../data/processed"):
    """
    Reads all MIDI files, extracts notes/chords and tonality (Major/Minor).
    Saves the parsed data for neural network training.
    """
    # Ensure directories exist
    os.makedirs(save_dir, exist_ok=True)
    
    parsed_songs = []
    
    # Find all .mid files in the directory
    midi_files = glob.glob(os.path.join(data_dir, "*.mid"))
    if not midi_files:
        print(f"WARNING: No MIDI files found in {data_dir}.")
        print("Please place some .mid files there before running this script.")
        return
        
    for file in midi_files:
        print(f"Parsing {file}...")
        try:
            # Load the MIDI file into music21
            midi = converter.parse(file)
            
            # 1. Extract Mood (Key Signature)
            # We analyze the tonality. Major = 0 (Happy), Minor = 1 (Sad).
            key_sig = midi.analyze('key')
            mood_label = 0 if key_sig.mode == 'major' else 1
            
            # 2. Extract Notes
            notes = []
            parts = instrument.partitionByInstrument(midi)
            
            # Grab the first instrument part (usually the melody/piano)
            if parts:
                notes_to_parse = parts.parts[0].recurse()
            else:
                notes_to_parse = midi.flat.notes
                
            for element in notes_to_parse:
                # If it's a single note, grab its pitch (e.g., "C4")
                if isinstance(element, note.Note):
                    notes.append(str(element.pitch))
                # If it's a chord, grab the normal order of its notes and join with dots (e.g., "4.7.11")
                elif isinstance(element, chord.Chord):
                    notes.append('.'.join(str(n) for n in element.normalOrder))
                    
            if len(notes) > 0:
                parsed_songs.append({
                    "filename": os.path.basename(file),
                    "mood": mood_label,
                    "notes": notes
                })
                
        except Exception as e:
            print(f"Error parsing {file}: {e}")
            
    # Save the extracted data into a pickle file so we don't have to re-parse every time
    output_path = os.path.join(save_dir, "parsed_songs.pkl")
    with open(output_path, 'wb') as filepath:
        pickle.dump(parsed_songs, filepath)
        
    print(f"\nSuccessfully processed {len(parsed_songs)} songs!")
    print(f"Data saved to {output_path}")

if __name__ == "__main__":
    print("Starting MIDI Preprocessing Pipeline...")
    
    # We use paths relative to this script's location
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(base_dir, "data", "raw_midi")
    processed_dir = os.path.join(base_dir, "data", "processed")
    
    preprocess_midi_data(data_dir=raw_dir, save_dir=processed_dir)
