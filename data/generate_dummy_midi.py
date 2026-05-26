import os
from music21 import stream, note, chord, instrument

def create_midi(filename, notes_list):
    """Utility to convert a list of note strings into a MIDI file"""
    s = stream.Score()
    p = stream.Part()
    p.insert(0, instrument.Piano())
    
    offset = 0
    for item in notes_list:
        if isinstance(item, list):
            c = chord.Chord(item)
            c.offset = offset
            c.quarterLength = 0.5
            p.append(c)
        else:
            n = note.Note(item)
            n.offset = offset
            n.quarterLength = 0.5
            p.append(n)
        offset += 0.5
        
    s.append(p)
    s.write('midi', fp=filename)

def generate_dummy_midi():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(base_dir, "raw")
    
    emotions = ["happy", "sad", "energetic", "romantic", "dark", "dreamy"]
    
    for em in emotions:
        folder = os.path.join(raw_dir, em)
        os.makedirs(folder, exist_ok=True)
        
        # Generate 2 dummy files per emotion to train the embedding layer
        for i in range(2):
            filepath = os.path.join(folder, f"dummy_{em}_{i}.mid")
            
            # Make the data slightly different per emotion just so the AI learns something
            if em == "happy":
                notes = ['C4', 'E4', 'G4', 'C5', ['C4', 'E4', 'G4']] * 10
            elif em == "sad":
                notes = ['A3', 'C4', 'E4', 'A4', ['A3', 'C4', 'E4']] * 10
            elif em == "energetic":
                notes = ['D4', 'D4', 'D5', 'D4', ['D4', 'F4', 'A4']] * 10
            elif em == "romantic":
                notes = ['E4', 'G#4', 'B4', 'E5', ['E4', 'G#4', 'B4']] * 10
            elif em == "dark":
                notes = ['C3', 'Eb3', 'Gb3', 'C4', ['C3', 'Eb3', 'Gb3']] * 10
            elif em == "dreamy":
                notes = ['F4', 'A4', 'C5', 'E5', ['F4', 'A4', 'C5', 'E5']] * 10
                
            create_midi(filepath, notes)
            
    print("Successfully generated dummy data for 6 emotions!")

if __name__ == "__main__":
    generate_dummy_midi()
