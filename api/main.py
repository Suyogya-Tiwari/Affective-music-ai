import os
import numpy as np
import pickle
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from tensorflow.keras.models import load_model
from music21 import instrument, note, chord, stream

# Initialize the FastAPI web server
app = FastAPI(title="NeuroComposer API")

# Allow our frontend website to communicate with this backend securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, we restrict this to your actual website URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the exact format of the JSON request the frontend will send us
class GenerateRequest(BaseModel):
    mood: str
    creativity: float = 0.8
    tempo: int = 120
    duration: int = 30

# Global variables to hold the AI brain in memory so it responds instantly
MODEL = None
PITCH_NAMES = None
# Global variables to hold the AI brain in memory so it responds instantly
MODEL = None
PITCH_NAMES = None
NOTE_TO_INT = None
INT_TO_NOTE = None
EMOTION_MAP = None
LOAD_ERROR = "Unknown"

def load_ai_assets():
    """Loads the trained weights and vocabulary into memory on server startup."""
    global MODEL, PITCH_NAMES, NOTE_TO_INT, INT_TO_NOTE, EMOTION_MAP, LOAD_ERROR
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "model", "model.weights.h5")
    data_path = os.path.join(base_dir, "data", "processed", "pitchnames.pkl")
    
    if not os.path.exists(model_path) or not os.path.exists(data_path):
        LOAD_ERROR = f"Files missing! model={os.path.exists(model_path)}, data={os.path.exists(data_path)}"
        print("WARNING: model.weights.h5 or pitchnames.pkl not found. You must train the model first!")
        return False
        
    try:
        import sys
        if base_dir not in sys.path:
            sys.path.append(base_dir)
        
        from model.network import create_network
        import pickle
        import json
        
        # Load the vocabulary mapping
        with open(data_path, 'rb') as f:
            PITCH_NAMES = pickle.load(f)
        
        # Create dictionaries to translate Numbers back into Musical Notes
        NOTE_TO_INT = dict((n, i) for i, n in enumerate(PITCH_NAMES))
        INT_TO_NOTE = dict((i, n) for i, n in enumerate(PITCH_NAMES))
        
        # Dynamically build the architecture natively so we don't rely on Keras JSON parsing!
        MODEL = create_network(sequence_length=100, vocab_size=len(PITCH_NAMES), num_emotions=6)
        
        # Load only the raw float weights from the file (100% immune to version mismatches)
        MODEL.load_weights(model_path)
        
        # Load Emotion Map
        emotion_map_path = os.path.join(base_dir, "data", "processed", "emotion_map.pkl")
        if os.path.exists(emotion_map_path):
            with open(emotion_map_path, 'rb') as f:
                EMOTION_MAP = pickle.load(f)
        else:
            EMOTION_MAP = {"happy": 0, "sad": 1, "energetic": 2, "romantic": 3, "dark": 4, "dreamy": 5}
            
        print("AI Model and assets successfully loaded into memory!")
        return True
    except Exception as e:
        import traceback
        LOAD_ERROR = traceback.format_exc()
        print(f"Error loading AI assets: {e}")
        return False

# Attempt to load the model immediately when the server boots up
load_ai_assets()

def sample_with_temperature(predictions, temperature=1.0):
    """
    Adjusts the probability distribution based on the creativity (temperature).
    Higher temp = more random/creative. Lower temp = safer/predictable.
    """
    predictions = np.asarray(predictions).astype('float64')
    # Math to adjust the probabilities
    predictions = np.log(predictions + 1e-7) / temperature
    exp_preds = np.exp(predictions)
    predictions = exp_preds / np.sum(exp_preds)
    
    # Roll a loaded dice to pick the next note based on the new probabilities
    probabilities = np.random.multinomial(1, predictions, 1)
    return np.argmax(probabilities)

@app.post("/generate")
async def generate_music(request: GenerateRequest):
    """The core endpoint that the website calls to get new music."""
    
    if MODEL is None or PITCH_NAMES is None:
        raise HTTPException(status_code=500, detail=f"Model failed to load: {LOAD_ERROR}")
        
    # 1. Translate Mood String to Integer
    mood_str = request.mood.lower()
    if mood_str not in EMOTION_MAP:
        # Fallback to happy if not found, or could raise an error
        mood_int = 0
    else:
        mood_int = EMOTION_MAP[mood_str]
        
    mood_input = np.array([mood_int])
    
    # 2. Create a random starting sequence (seed) to kickstart the AI
    sequence_length = MODEL.input_shape[0][1]
    pattern = np.random.randint(0, len(PITCH_NAMES)-1, size=(sequence_length,))
    
    prediction_output = []
    
    # Calculate exactly how many notes are needed to fill the requested duration
    # We must account for the Humanizer's different note lengths based on the emotion!
    avg_dur = 0.55
    if mood_str == "sad": avg_dur = 0.8
    elif mood_str == "dark": avg_dur = 1.0
    elif mood_str == "happy": avg_dur = 0.45
    elif mood_str == "energetic": avg_dur = 0.3
    elif mood_str == "dreamy": avg_dur = 0.7
    elif mood_str == "romantic": avg_dur = 0.65
    
    # tempo / 60 = Beats Per Second. 
    total_beats_needed = (request.tempo / 60.0) * request.duration
    notes_to_generate = int(total_beats_needed / avg_dur)
    
    # 3. Generate new notes one-by-one
    for _ in range(notes_to_generate):
        # Format input for the model
        prediction_input = np.reshape(pattern, (1, sequence_length, 1))
        prediction_input = prediction_input / float(len(PITCH_NAMES))
        
        # Predict the next note!
        prediction = MODEL.predict([prediction_input, mood_input], verbose=0)
        
        # Apply the creativity slider (temperature)
        index = sample_with_temperature(prediction[0], request.creativity)
        
        # Save the predicted note
        result = INT_TO_NOTE[index]
        prediction_output.append(result)
        
        # Slide the window forward for the next loop
        pattern = np.append(pattern, index)
        pattern = pattern[1:]
        
    # --- CONSTRAINED DECODING SCALES ---
    # We define the strict music theory intervals (Pitch Classes) for each emotion.
    # 0=C, 1=C#, 2=D, 3=D#, 4=E, 5=F, 6=F#, 7=G, 8=G#, 9=A, 10=A#, 11=B
    SCALES = {
        "happy": [0, 2, 4, 5, 7, 9, 11],       # C Major (Bright, uplifting)
        "sad": [0, 2, 3, 5, 7, 8, 10],         # C Minor (Melancholy)
        "dark": [0, 1, 3, 5, 7, 8, 10],        # C Phrygian (Ominous, dark)
        "energetic": [0, 2, 4, 5, 7, 9, 10],   # C Mixolydian (Driving, bouncy)
        "romantic": [1, 3, 5, 6, 8, 10, 0],    # Db Major (Rich, warm)
        "dreamy": [0, 2, 4, 6, 7, 9, 11],      # C Lydian (Ethereal, floaty)
    }
    
    current_scale = SCALES.get(mood_str, SCALES["happy"])
    
    def snap_to_scale(midi_pitch, allowed_intervals):
        """Mathematical Autocorrect: Forces a wrong note into the correct emotional scale."""
        octave = midi_pitch // 12
        pitch_class = midi_pitch % 12
        # Find the absolute closest allowed note in the scale
        closest_pitch = min(allowed_intervals, key=lambda x: min(abs(x - pitch_class), 12 - abs(x - pitch_class)))
        return (octave * 12) + closest_pitch

    # 4. Convert the list of predicted strings back into a physical MIDI file
    offset = 0
    output_notes = []
    final_tempo = request.tempo
    
    for pattern_str in prediction_output:
        import random
        
        # --- CONSTRAINED VELOCITY & SUSTAIN PEDAL SCALING ---
        # We respect your chosen Tempo slider, but we force Velocity and Sustain
        sustain_multiplier = 1.0 # Default: No overlap
        
        if mood_str == "sad":
            dur = random.uniform(0.6, 1.0)
            vel = random.randint(50, 75)
            sustain_multiplier = 2.0 # Slight bleed
        elif mood_str == "dark":
            dur = random.uniform(0.8, 1.2)
            vel = random.randint(40, 70)
            sustain_multiplier = 2.5 # Brooding bleed
        elif mood_str == "happy":
            dur = random.uniform(0.3, 0.6)
            vel = random.randint(85, 110)
            sustain_multiplier = 1.0 # Staccato, punchy
        elif mood_str == "energetic":
            dur = random.uniform(0.2, 0.4)
            vel = random.randint(100, 127)
            sustain_multiplier = 0.8 # Very punchy, aggressive
        elif mood_str == "dreamy":
            dur = random.uniform(0.5, 0.9)
            vel = random.randint(60, 85)
            sustain_multiplier = 6.0 # Massive sustain pedal, notes ring forever
        elif mood_str == "romantic":
            dur = random.uniform(0.5, 0.8)
            vel = random.randint(70, 95)
            sustain_multiplier = 4.0 # Heavy sustain
        else:
            dur = random.uniform(0.4, 0.7)
            vel = random.randint(70, 115)
            
        physical_dur = dur * sustain_multiplier
            
        # Parse the AI's prediction
        if ('.' in pattern_str) or pattern_str.isdigit():
            notes_in_chord = pattern_str.split('.')
            notes = []
            for current_note in notes_in_chord:
                pitch_val = int(current_note) + 60
                
                # Apply Octave Constraints for specific vibes
                if mood_str == "dark": pitch_val -= 12   # Shift bass down
                if mood_str == "dreamy": pitch_val += 12 # Shift treble up
                
                # THE AUTOCORRECT FILTER: Snap note to the strict emotion scale
                pitch_val = snap_to_scale(pitch_val, current_scale)
                
                new_note = note.Note(pitch_val)
                new_note.storedInstrument = instrument.Piano()
                new_note.volume.velocity = vel
                notes.append(new_note)
            new_chord = chord.Chord(notes)
            new_chord.offset = offset
            new_chord.quarterLength = physical_dur
            output_notes.append(new_chord)
        else:
            new_note = note.Note(pattern_str)
            pitch_val = new_note.pitch.midi
            
            # Apply Octave Constraints
            if mood_str == "dark": pitch_val -= 12
            if mood_str == "dreamy": pitch_val += 12
            
            # THE AUTOCORRECT FILTER
            pitch_val = snap_to_scale(pitch_val, current_scale)
            
            new_note = note.Note(pitch_val)
            new_note.offset = offset
            new_note.quarterLength = physical_dur
            new_note.volume.velocity = vel
            new_note.storedInstrument = instrument.Piano()
            output_notes.append(new_note)
            
        # The next note starts based on the original dur (plus rubato swing), 
        # allowing the physical_dur to bleed over it!
        offset += dur + random.uniform(0.0, 0.08)
        
    # 4. Convert notes to a proper MIDI file
    from music21 import stream, tempo, instrument as m21_instrument
    
    score = stream.Score()
    part = stream.Part()
    
    # Add essential MIDI headers that Web Players require
    part.insert(0, m21_instrument.Piano())
    part.insert(0, tempo.MetronomeMark(number=final_tempo))
    
    # Insert all generated notes
    for n in output_notes:
        part.insert(n.offset, n)
        
    score.insert(0, part)
    
    output_filepath = os.path.join(os.path.dirname(__file__), "generated_track.mid")
    score.write('midi', fp=output_filepath)
    
    # 5. Send the physical .mid file back over the internet to the user's browser
    return {"status": "Success", "message": "Track generated successfully."}

@app.get("/track")
async def get_track():
    output_filepath = os.path.join(os.path.dirname(__file__), "generated_track.mid")
    if os.path.exists(output_filepath):
        from fastapi.responses import FileResponse
        return FileResponse(output_filepath, media_type="audio/midi")
    return {"error": "Track not found"}

@app.get("/")
def read_root():
    return {"status": "NeuroComposer API is running!"}
