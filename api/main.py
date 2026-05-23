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

# Global variables to hold the AI brain in memory so it responds instantly
MODEL = None
PITCH_NAMES = None
NOTE_TO_INT = None
INT_TO_NOTE = None
EMOTION_MAP = None

def load_ai_assets():
    """Loads the trained weights and vocabulary into memory on server startup."""
    global MODEL, PITCH_NAMES, NOTE_TO_INT, INT_TO_NOTE, EMOTION_MAP
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "model", "model.h5")
    data_path = os.path.join(base_dir, "data", "processed", "network_data.npz")
    
    if not os.path.exists(model_path) or not os.path.exists(data_path):
        print("WARNING: model.h5 or network_data.npz not found. You must train the model first!")
        return False
        
    try:
        # Load the Keras brain
        MODEL = load_model(model_path)
        
        # Load the vocabulary mapping
        data = np.load(data_path, allow_pickle=True)
        PITCH_NAMES = data['pitchnames']
        
        # Create dictionaries to translate Numbers back into Musical Notes
        NOTE_TO_INT = dict((n, i) for i, n in enumerate(PITCH_NAMES))
        INT_TO_NOTE = dict((i, n) for i, n in enumerate(PITCH_NAMES))
        
        # Load Emotion Map
        emotion_map_path = os.path.join(base_dir, "data", "processed", "emotion_map.pkl")
        if os.path.exists(emotion_map_path):
            with open(emotion_map_path, 'rb') as f:
                EMOTION_MAP = pickle.load(f)
        else:
            EMOTION_MAP = {"happy": 0, "sad": 1}
            
        print("AI Model and assets successfully loaded into memory!")
        return True
    except Exception as e:
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
        raise HTTPException(status_code=500, detail="AI Model not trained yet. Run train.py first!")
        
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
    
    # 3. Generate 100 new notes one-by-one
    for _ in range(100):
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
        
    # 4. Convert the list of predicted strings back into a physical MIDI file
    offset = 0
    output_notes = []
    
    for pattern_str in prediction_output:
        # If the AI predicted a Chord (e.g., '4.7.11')
        if ('.' in pattern_str) or pattern_str.isdigit():
            notes_in_chord = pattern_str.split('.')
            notes = []
            for current_note in notes_in_chord:
                # normalOrder gives 0-11. We shift it to octave 4 (+60)
                new_note = note.Note(int(current_note) + 60)
                new_note.storedInstrument = instrument.Piano()
                notes.append(new_note)
            new_chord = chord.Chord(notes)
            new_chord.offset = offset
            new_chord.quarterLength = 0.5
            output_notes.append(new_chord)
        # If the AI predicted a single Note (e.g., 'C4')
        else:
            new_note = note.Note(pattern_str)
            new_note.offset = offset
            new_note.quarterLength = 0.5
            new_note.storedInstrument = instrument.Piano()
            output_notes.append(new_note)
            
        # Increase offset so notes play sequentially, not all at the exact same time
        offset += 0.5
        
    # 4. Convert notes to a proper MIDI file
    from music21 import stream, tempo, instrument as m21_instrument
    
    score = stream.Score()
    part = stream.Part()
    
    # Add essential MIDI headers that Web Players require
    part.insert(0, m21_instrument.Piano())
    part.insert(0, tempo.MetronomeMark(number=request.tempo))
    
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
        return FileResponse(output_filepath, media_type="audio/midi")
    return {"error": "Track not found"}

@app.get("/")
def read_root():
    return {"status": "NeuroComposer API is running!"}
