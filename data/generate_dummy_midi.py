import os
from music21 import stream, note, chord

def generate_midi(filename, notes_data):
    s = stream.Score()
    p = stream.Part()
    for n in notes_data:
        if isinstance(n, list):
            c = chord.Chord(n)
            c.quarterLength = 0.5
            p.append(c)
        else:
            new_note = note.Note(n)
            new_note.quarterLength = 0.5
            p.append(new_note)
    s.append(p)
    s.write('midi', fp=filename)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(base_dir, "raw_midi")
    happy_dir = os.path.join(raw_dir, "happy")
    sad_dir = os.path.join(raw_dir, "sad")
    os.makedirs(happy_dir, exist_ok=True)
    os.makedirs(sad_dir, exist_ok=True)
    
    print("Generating synthetic Happy (Major) MIDI files...")
    for i in range(5):
        # Simple C major arpeggios and chords
        notes = ['C4', 'E4', 'G4', 'C5', ['C4', 'E4', 'G4'], 'F4', 'A4', 'C5', ['F4', 'A4', 'C5'], 'G4', 'B4', 'D5', ['G4', 'B4', 'D5']] * 10
        generate_midi(os.path.join(happy_dir, f"happy_{i}.mid"), notes)
        
    print("Generating synthetic Sad (Minor) MIDI files...")
    for i in range(5):
        # Simple A minor arpeggios and chords
        notes = ['A3', 'C4', 'E4', 'A4', ['A3', 'C4', 'E4'], 'D4', 'F4', 'A4', ['D4', 'F4', 'A4'], 'E4', 'G#4', 'B4', ['E4', 'G#4', 'B4']] * 10
        generate_midi(os.path.join(sad_dir, f"sad_{i}.mid"), notes)

    print("Synthetic MIDI dataset generated successfully!")

if __name__ == "__main__":
    main()
