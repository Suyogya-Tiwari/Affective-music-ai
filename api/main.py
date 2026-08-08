import os
import numpy as np
import pickle
import tensorflow as tf
import subprocess
import shutil
import zipfile
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from tensorflow.keras.models import load_model
from music21 import instrument, note, chord, stream
import librosa

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
    seed_notes: list[str] = []
    instrument: int = 0
    include_drums: bool = False
    include_chords_bass: bool = False
    chord_progression: str = "auto"
    locked_stems: list[str] = []
    drum_groove: str = "auto"

# Global variables to hold the AI brain in memory so it responds instantly
MODEL = None
PITCH_NAMES = None
NOTE_TO_INT = None
INT_TO_NOTE = None
EMOTION_MAP = None
LOAD_ERROR = ""
FAST_PREDICT_FN = None

def load_ai_assets():
    """Loads the trained weights and vocabulary into memory on server startup."""
    global MODEL, PITCH_NAMES, NOTE_TO_INT, INT_TO_NOTE, EMOTION_MAP, LOAD_ERROR, FAST_PREDICT_FN
    
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
            
        # Compile the Keras prediction into a static execution graph for 10x-50x speedups
        @tf.function(input_signature=[
            tf.TensorSpec(shape=(1, 100, 1), dtype=tf.float32),
            tf.TensorSpec(shape=(1,), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.int32),
            tf.TensorSpec(shape=(), dtype=tf.float32)
        ])
        def fast_autoregressive_generate(seq_in, mood_in, num_notes, creativity):
            outputs = tf.TensorArray(dtype=tf.int32, size=0, dynamic_size=True)
            curr_seq = seq_in
            
            for i in tf.range(num_notes):
                preds = MODEL([curr_seq, mood_in], training=False)
                
                # Temperature sampling directly in TensorFlow graph
                preds_adj = tf.math.log(preds[0] + 1e-7) / creativity
                sampled_id = tf.random.categorical([preds_adj], 1, dtype=tf.int32)[0, 0]
                
                outputs = outputs.write(i, sampled_id)
                
                # Shift sequence window (Vocab size is 38)
                sampled_float = tf.cast(sampled_id, tf.float32) / 38.0
                sampled_tensor = tf.reshape(sampled_float, (1, 1, 1))
                curr_seq = tf.concat([curr_seq[:, 1:, :], sampled_tensor], axis=1)
                
            return outputs.stack()
            
        FAST_PREDICT_FN = fast_autoregressive_generate
            
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
    
    # 2. Create a starting sequence (seed) to kickstart the AI
    sequence_length = MODEL.input_shape[0][1]
    
    if request.seed_notes and len(request.seed_notes) > 0:
        seed_ints = []
        for note_name in request.seed_notes:
            try:
                # Convert 'C4' to MIDI 60, then to string '60' for vocabulary lookup
                n = note.Note(note_name)
                pitch_str = str(n.pitch.midi)
                if pitch_str in NOTE_TO_INT:
                    seed_ints.append(NOTE_TO_INT[pitch_str])
            except Exception:
                pass
                
        if len(seed_ints) > 0:
            # Loop the seed sequence to fill the required input length
            pattern = []
            while len(pattern) < sequence_length:
                pattern.extend(seed_ints)
            # Truncate to exact length
            pattern = np.array(pattern[:sequence_length])
        else:
            pattern = np.random.randint(0, len(PITCH_NAMES)-1, size=(sequence_length,))
    else:
        # Standard random start
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
    
    import time
    start_lstm = time.time()
    
    # 3. Generate all new notes in ONE MASSIVE C++ BATCH!
    prediction_input = np.reshape(pattern, (1, sequence_length, 1))
    prediction_input = prediction_input / float(len(PITCH_NAMES))
    
    tf_seq = tf.constant(prediction_input, dtype=tf.float32)
    tf_mood = tf.constant(mood_input, dtype=tf.float32)
    tf_num_notes = tf.constant(notes_to_generate, dtype=tf.int32)
    tf_creativity = tf.constant(request.creativity, dtype=tf.float32)
    
    # Run the entire autoregressive loop inside the C++ graph
    generated_indices = FAST_PREDICT_FN(tf_seq, tf_mood, tf_num_notes, tf_creativity).numpy()
    
    for index in generated_indices:
        result = INT_TO_NOTE[index]
        prediction_output.append(result)
        
    end_lstm = time.time()
    print(f"LSTM Generation took {end_lstm - start_lstm:.2f} seconds for {notes_to_generate} notes.", flush=True)
        
    # --- PRE-GENERATE CHORD PROGRESSION ---
    # We must generate the chords BEFORE the melody so we can snap the melody to the chords!
    import random
    
    CHORD_PROGRESSIONS = {
        "happy": [(48, "M"), (53, "M"), (57, "m"), (55, "M")], # C - F - Am - G
        "sad": [(48, "m"), (56, "M"), (51, "M"), (58, "M")], # Cm - Ab - Eb - Bb
        "dark": [(48, "m"), (49, "M"), (48, "m"), (55, "M")], # Cm - Db - Cm - G
        "energetic": [(48, "M"), (58, "M"), (53, "M"), (48, "M")], # C - Bb - F - C
        "romantic": [(49, "M"), (58, "m"), (53, "m"), (56, "M")], # Db - Bbm - Fm - Ab
        "dreamy": [(48, "M"), (50, "M"), (52, "m"), (53, "M")], # C - D - Em - F
    }
    
    # Default to the emotional progression
    chord_progression = CHORD_PROGRESSIONS.get(mood_str, CHORD_PROGRESSIONS["happy"])
    
    # Music Theory Overrides!
    if request.chord_progression == "pop":
        chord_progression = [(48, "M"), (55, "M"), (57, "m"), (53, "M")] # I-V-vi-IV (C - G - Am - F)
    elif request.chord_progression == "jazz":
        chord_progression = [(50, "m"), (55, "M"), (48, "M"), (57, "m")] # ii-V-I-vi (Dm - G - C - Am)
    elif request.chord_progression == "cinematic":
        chord_progression = [(48, "m"), (56, "M"), (51, "M"), (59, "M")] # i-VI-III-VII (Cm - Ab - Eb - B)
    elif request.chord_progression == "auto":
        # TRUE AI "AUTO" CHORD GENERATION
        # Algorithmic Markov Chain using diatonic degrees scaled by Creativity
        scale_intervals = [0, 2, 4, 5, 7, 9, 11] # Major
        if mood_str in ["sad", "dark", "romantic"]:
            scale_intervals = [0, 2, 3, 5, 7, 8, 10] # Minor
        
        chord_progression = []
        curr_degree = 0 # Start on root (I)
        for _ in range(4):
            midi_note = 48 + scale_intervals[curr_degree]
            
            # Determine chord quality (Major, Minor, Dim) based on scale degree
            if mood_str in ["sad", "dark", "romantic"]:
                quality = "m" if curr_degree in [0, 3, 4] else "M"
            else:
                quality = "M" if curr_degree in [0, 3, 4] else "m"
                
            if (mood_str in ["sad", "dark", "romantic"] and curr_degree == 1) or \
               (mood_str not in ["sad", "dark", "romantic"] and curr_degree == 6):
                quality = "m" # Fallback diminished to minor to avoid dissonance
                
            chord_progression.append((midi_note, quality))
            
            # Advanced Algorithmic Progression (Random Walk based on Creativity)
            if request.creativity > 1.0:
                curr_degree = random.choice([0, 1, 2, 3, 4, 5, 6])
            else:
                # Safe diatonic transitions
                if curr_degree == 0: curr_degree = random.choice([3, 4, 5])
                elif curr_degree in [3, 4]: curr_degree = random.choice([0, 5])
                elif curr_degree == 5: curr_degree = random.choice([3, 4])
                else: curr_degree = 0

    def snap_to_chord(midi_pitch, chord_root, chord_type):
        """Mathematical Autocorrect: Forces a wrong note into the specific chord's pentatonic scale."""
        if chord_type == "M":
            intervals = [0, 2, 4, 7, 9] # Major pentatonic
        else:
            intervals = [0, 3, 5, 7, 10] # Minor pentatonic
            
        chord_root_class = chord_root % 12
        allowed_classes = [(chord_root_class + i) % 12 for i in intervals]
        pitch_class = midi_pitch % 12
        
        closest_class = min(allowed_classes, key=lambda x: min(abs(x - pitch_class), 12 - abs(x - pitch_class)))
        diff = closest_class - pitch_class
        if diff > 6: diff -= 12
        elif diff < -6: diff += 12
        return midi_pitch + diff

    # 4. Convert the list of predicted strings back into a physical MIDI file
    offset = 0
    output_notes = []
    final_tempo = request.tempo
    
    # Create the requested Instrument Object using instrumentFromMidiProgram to force MIDI Program Change
    target_instrument = instrument.instrumentFromMidiProgram(request.instrument)
    
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
            vel = random.randint(55, 80)
            sustain_multiplier = 6.0 # Massive sustain pedal, notes ring forever
        elif mood_str == "romantic":
            dur = random.uniform(0.5, 0.8)
            vel = random.randint(65, 95)
            sustain_multiplier = 4.0 # Heavy sustain
        else:
            dur = random.uniform(0.4, 0.7)
            vel = random.randint(70, 110)
            
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
                
                # --- HARMONIC CHORD-SNAPPING & QUANTIZATION ---
                measure_index = int(offset // 4)
                chord_index = measure_index % len(chord_progression)
                current_chord_root, current_chord_type = chord_progression[chord_index]
                pitch_val = snap_to_chord(pitch_val, current_chord_root, current_chord_type)
                
                # Hard Quantize Rhythm to 16th Notes (0.25)
                quantized_offset = round(offset * 4) / 4.0
                quantized_dur = max(0.25, round(physical_dur * 4) / 4.0)
                
                new_note = note.Note(pitch_val)
                new_note.storedInstrument = target_instrument
                new_note.volume.velocity = vel
                notes.append(new_note)
            new_chord = chord.Chord(notes)
            new_chord.offset = quantized_offset
            new_chord.quarterLength = quantized_dur
            output_notes.append(new_chord)
        else:
            new_note = note.Note(pattern_str)
            pitch_val = new_note.pitch.midi
            
            # Apply Octave Constraints
            if mood_str == "dark": pitch_val -= 12
            if mood_str == "dreamy": pitch_val += 12
            
            # MELODIC SMOOTHING: Prevent chaotic, unmusical jumps
            if len(output_notes) > 0:
                prev_note = output_notes[-1]
                if hasattr(prev_note, 'pitch'):
                    prev_pitch = prev_note.pitch.midi
                    while pitch_val > prev_pitch + 9: # Max jump of a 6th
                        pitch_val -= 12
                    while pitch_val < prev_pitch - 9:
                        pitch_val += 12
            
            # --- HARMONIC CHORD-SNAPPING & QUANTIZATION ---
            measure_index = int(offset // 4)
            chord_index = measure_index % len(chord_progression)
            current_chord_root, current_chord_type = chord_progression[chord_index]
            pitch_val = snap_to_chord(pitch_val, current_chord_root, current_chord_type)
            
            # Hard Quantize Rhythm to 16th Notes (0.25)
            quantized_offset = round(offset * 4) / 4.0
            quantized_dur = max(0.25, round(physical_dur * 4) / 4.0)
            
            new_note = note.Note(pitch_val)
            new_note.offset = quantized_offset
            new_note.quarterLength = quantized_dur
            new_note.volume.velocity = vel
            new_note.storedInstrument = target_instrument
            output_notes.append(new_note)
            
        # The next note starts based on the original dur (plus rubato swing), 
        # allowing the physical_dur to bleed over it!
        offset += dur + random.uniform(0.0, 0.08)
        if offset >= total_beats_needed:
            break
        
    # 4. Convert notes to a proper MIDI file
    from music21 import stream, tempo, instrument as m21_instrument
    
    score = stream.Score()
    part = stream.Part()
    
    # Add essential MIDI headers that Web Players require
    part.insert(0, target_instrument)
    part.insert(0, tempo.MetronomeMark(number=final_tempo))
    
    # Insert all generated notes
    for n in output_notes:
        part.insert(n.offset, n)
        
    # Seed notes prepended to output to ensure playback of co-pilot melody!
    if request.seed_notes and len(request.seed_notes) > 0:
        seed_offset = 0
        for sn in request.seed_notes:
            try:
                sn_note = note.Note(sn)
                sn_note.quarterLength = 0.5
                sn_note.offset = seed_offset
                sn_note.volume.velocity = 100
                sn_note.storedInstrument = target_instrument
                # Shift all AI generated notes forward by 0.5 beats to make room
                for n in part.notes:
                    n.offset += 0.5
                part.insert(seed_offset, sn_note)
                seed_offset += 0.5
            except Exception:
                pass

    score.insert(0, part)
    
    # --- FULL BAND GENERATION (CHORDS & BASS) ---
    if request.include_chords_bass:
        
        chord_part = stream.Part()
        bass_part = stream.Part()
        
        # Dynamic Acoustic Instruments instead of Synths
        lead_is_piano = request.instrument in [0, 1, 2, 3, 4, 5, 6, 7]
        chord_midi = 48 if lead_is_piano else 0 # Strings (48) or Acoustic Grand Piano (0)
        bass_midi = 32 # Acoustic Bass
        
        chord_inst = instrument.instrumentFromMidiProgram(chord_midi)
        chord_part.insert(0, chord_inst)
        chord_part.insert(0, tempo.MetronomeMark(number=final_tempo))
        
        bass_inst = instrument.instrumentFromMidiProgram(bass_midi)
        bass_part.insert(0, bass_inst)
        bass_part.insert(0, tempo.MetronomeMark(number=final_tempo))
        
        total_beats = int((request.tempo / 60.0) * request.duration)
        
        for b in range(0, total_beats, 4):
            # Pick the chord for this measure
            chord_index = (b // 4) % len(chord_progression)
            root_midi, chord_type = chord_progression[chord_index]
            
            chord_len = min(4.0, total_beats - b)
            
            # Build the Chord
            chord_notes = [root_midi, root_midi + (4 if chord_type == "M" else 3), root_midi + 7]
            chord_notes.append(root_midi + 12) # Add octave for thickness
            
            c = chord.Chord(chord_notes)
            c.offset = b
            c.quarterLength = chord_len
            c.volume.velocity = random.randint(45, 60)
            c.storedInstrument = chord_inst # FORCE INSTRUMENT
            chord_part.insert(c.offset, c)
            
            # Build the Groove-Locked Bassline
            bass_root = root_midi - 12 # Octave lower
            
            if mood_str in ["energetic", "happy"]:
                # Syncopated Dance Bass (16th note groove)
                for beat_offset in range(4):
                    if b + beat_offset >= total_beats: break
                    # Alternate between on-beat punch and syncopated bounce
                    pattern = [(0, 0.5, 85), (0.75, 0.25, 70)] if beat_offset % 2 == 0 else [(0.25, 0.25, 75), (0.5, 0.5, 85)]
                    for (pos, dur, vel) in pattern:
                        n = note.Note(bass_root)
                        n.offset = b + beat_offset + pos
                        n.quarterLength = dur
                        n.volume.velocity = vel
                        n.storedInstrument = bass_inst
                        bass_part.insert(n.offset, n)
            elif mood_str == "dark":
                # Rolling 8th notes (driving tension)
                for beat_offset in range(4):
                    if b + beat_offset >= total_beats: break
                    for pos in [0, 0.5]:
                        n = note.Note(bass_root)
                        n.offset = b + beat_offset + pos
                        n.quarterLength = 0.5
                        n.volume.velocity = 80 if pos == 0 else 65
                        n.storedInstrument = bass_inst
                        bass_part.insert(n.offset, n)
            else:
                # Standard Quarter notes for Dreamy/Sad/Romantic
                for beat_offset in range(4):
                    if b + beat_offset >= total_beats: break
                    n = note.Note(bass_root)
                    n.offset = b + beat_offset
                    n.quarterLength = 1.0
                    n.volume.velocity = 75
                    n.storedInstrument = bass_inst
                    bass_part.insert(n.offset, n)
                    
        score.insert(0, chord_part)
        score.insert(0, bass_part)
    
    # --- ALGORITHMIC DRUMS GENERATION ---
    if request.include_drums:
        drum_part = stream.Part()
        drum_inst = instrument.Percussion()
        drum_inst.midiChannel = 9 # Force MIDI Channel 10
        drum_part.insert(0, drum_inst)
        drum_part.insert(0, tempo.MetronomeMark(number=final_tempo))
        
        total_beats = int((request.tempo / 60.0) * request.duration)
        for b in range(total_beats):
            
            # --- Drum Groove Logic ---
            groove = request.drum_groove
            is_kick = False
            is_snare = False
            is_hat = False
            
            if groove == "auto":
                # TRUE AI "AUTO" DRUM GENERATION
                # Uses algorithmic probability models scaled by the user's creativity parameter
                if b % 4 == 0: is_kick = True
                elif b % 4 == 2 and request.creativity > 0.8: is_kick = random.random() < 0.3
                elif b % 2 != 0: is_kick = random.random() < (request.creativity * 0.2)
                
                if b % 4 == 2: is_snare = True
                elif b % 2 != 0: is_snare = random.random() < (request.creativity * 0.15)
                
                is_hat = random.random() < min(1.0, 0.4 + (request.creativity * 0.4))
                
                if request.creativity > 1.2 and b % 4 == 3: is_kick = True
                
            elif groove == "house":
                is_kick = True # Every quarter note
                is_snare = (b % 2 != 0) # Beats 2 and 4
                is_hat = True
            elif groove == "hiphop":
                is_kick = (b % 4 == 0)
                is_snare = (b % 4 == 1) or (b % 4 == 3) # Beats 2 and 4
                is_hat = True
                # Add syncopated 8th note kick (Beat 2.5)
                if b % 4 == 1:
                    k2 = note.Note(36); k2.offset = b + 0.5; k2.quarterLength = 0.5; k2.volume.velocity = 90; k2.storedInstrument = drum_inst; drum_part.insert(k2.offset, k2)
            elif groove == "rock":
                is_kick = (b % 2 == 0) # Beats 1 and 3
                is_snare = (b % 2 != 0) # Beats 2 and 4
                is_hat = True
            elif groove == "trap":
                is_kick = (b % 4 == 0)
                is_snare = (b % 4 == 2) # Beat 3
                is_hat = True
                # 16th note hi-hat rolls and syncopated kicks
                if b % 4 == 1:
                    k2 = note.Note(36); k2.offset = b + 0.5; k2.quarterLength = 0.5; k2.volume.velocity = 95; k2.storedInstrument = drum_inst; drum_part.insert(k2.offset, k2)
                if b % 4 == 2:
                    k3 = note.Note(36); k3.offset = b + 0.5; k3.quarterLength = 0.5; k3.volume.velocity = 95; k3.storedInstrument = drum_inst; drum_part.insert(k3.offset, k3)
                if b % 4 == 3:
                    h2 = note.Note(42); h2.offset = b + 0.25; h2.quarterLength = 0.25; h2.volume.velocity = 70; h2.storedInstrument = drum_inst; drum_part.insert(h2.offset, h2)
                    h3 = note.Note(42); h3.offset = b + 0.75; h3.quarterLength = 0.25; h3.volume.velocity = 70; h3.storedInstrument = drum_inst; drum_part.insert(h3.offset, h3)
            elif groove == "reggaeton":
                is_kick = True # Four on the floor
                is_hat = True
                # Tresillo snare on 1.75, 2.5, 3.75, 4.5
                s1 = note.Note(38); s1.offset = b + 0.75; s1.quarterLength = 0.25; s1.volume.velocity = 90; s1.storedInstrument = drum_inst; drum_part.insert(s1.offset, s1)
                if b % 2 == 0:
                    s2 = note.Note(38); s2.offset = b + 1.5; s2.quarterLength = 0.5; s2.volume.velocity = 90; s2.storedInstrument = drum_inst; drum_part.insert(s2.offset, s2)
            elif groove == "disco":
                is_kick = True
                is_snare = (b % 2 != 0)
                # Open hi-hat on the upbeat
                h_open = note.Note(46); h_open.offset = b + 0.5; h_open.quarterLength = 0.5; h_open.volume.velocity = 90; h_open.storedInstrument = drum_inst; drum_part.insert(h_open.offset, h_open)
            elif groove == "euclidean":
                # Advanced Polyrhythmic Euclidean Generator (e.g., E(5,16) kick, E(4,16) snare, E(13,16) hats)
                def get_euclidean_hit(step_idx, pulses, steps, offset=0):
                    idx = (step_idx - offset) % steps
                    return (idx * pulses) % steps < pulses

                for beat_offset in range(4): # 4 sixteenth notes per beat
                    global_16th = int(b * 4) + beat_offset
                    
                    # Kick: E(5, 16)
                    if get_euclidean_hit(global_16th, 5, 16):
                        k = note.Note(36)
                        k.offset = b + (beat_offset * 0.25)
                        k.quarterLength = 0.25
                        k.volume.velocity = 90 if beat_offset == 0 else 75
                        k.storedInstrument = drum_inst
                        drum_part.insert(k.offset, k)
                    
                    # Snare: E(4, 16, offset=4) -> Hits on backbeats mostly
                    if get_euclidean_hit(global_16th, 4, 16, offset=4):
                        s = note.Note(38)
                        s.offset = b + (beat_offset * 0.25)
                        s.quarterLength = 0.25
                        s.volume.velocity = 95
                        s.storedInstrument = drum_inst
                        drum_part.insert(s.offset, s)
                        
                    # Hats: E(13, 16)
                    if get_euclidean_hit(global_16th, 13, 16):
                        h = note.Note(42)
                        h.offset = b + (beat_offset * 0.25)
                        h.quarterLength = 0.25
                        h.volume.velocity = random.randint(60, 80)
                        h.storedInstrument = drum_inst
                        drum_part.insert(h.offset, h)
                        
                # Disable standard processing since we handled all 16ths above
                is_kick = False
                is_snare = False
                is_hat = False
            elif groove == "dnb":
                is_kick = (b % 4 == 0)
                is_snare = (b % 4 == 1) or (b % 4 == 3)
                is_hat = True
                # Breakbeat syncopation
                if b % 4 == 2:
                    k2 = note.Note(36); k2.offset = b + 0.5; k2.quarterLength = 0.5; k2.volume.velocity = 90; k2.storedInstrument = drum_inst; drum_part.insert(k2.offset, k2)
            elif groove == "bossa":
                is_kick = True # Kick on every beat
                is_hat = True
                # Clave/Rimshot pattern
                if b % 4 == 0:
                    s1 = note.Note(37); s1.offset = b; s1.quarterLength = 0.5; s1.volume.velocity = 90; s1.storedInstrument = drum_inst; drum_part.insert(s1.offset, s1)
                    s2 = note.Note(37); s2.offset = b + 1.5; s2.quarterLength = 0.5; s2.volume.velocity = 90; s2.storedInstrument = drum_inst; drum_part.insert(s2.offset, s2)
                elif b % 4 == 2:
                    s3 = note.Note(37); s3.offset = b + 0.5; s3.quarterLength = 0.5; s3.volume.velocity = 90; s3.storedInstrument = drum_inst; drum_part.insert(s3.offset, s3)
            elif groove == "synthwave":
                is_kick = True
                is_snare = (b % 2 != 0)
                is_hat = True
            elif groove == "lofi":
                is_kick = (b % 4 == 0)
                is_snare = (b % 4 == 1) or (b % 4 == 3)
                # Swung hi-hats
                is_hat = True
                h_swing = note.Note(42); h_swing.offset = b + 0.66; h_swing.quarterLength = 0.33; h_swing.volume.velocity = 60; h_swing.storedInstrument = drum_inst; drum_part.insert(h_swing.offset, h_swing)
                
            if is_kick:
                kick = note.Note(36)
                kick.offset = b
                kick.quarterLength = 1.0
                kick.volume.velocity = 100
                kick.storedInstrument = drum_inst # FORCE CHANNEL
                drum_part.insert(kick.offset, kick)
                
            if is_snare:
                snare = note.Note(38)
                snare.offset = b
                snare.quarterLength = 1.0
                snare.volume.velocity = random.randint(85, 95)
                snare.storedInstrument = drum_inst # FORCE CHANNEL
                drum_part.insert(snare.offset, snare)
            
            # Dynamic Hi-Hats
            if is_hat:
                hh1 = note.Note(42)
                hh1.offset = b
                hh1.quarterLength = 0.5
                hh1.volume.velocity = 80
                hh1.storedInstrument = drum_inst # FORCE CHANNEL
                drum_part.insert(hh1.offset, hh1)
                
                if groove != "hiphop" or b % 2 != 0: # Add ghost note
                    hh2 = note.Note(42)
                    hh2.offset = b + 0.5
                    hh2.quarterLength = 0.5
                    hh2.volume.velocity = 55
                    hh2.storedInstrument = drum_inst # FORCE CHANNEL
                    drum_part.insert(hh2.offset, hh2)
            
        score.insert(0, drum_part)
    
    output_filepath = os.path.join(os.path.dirname(__file__), "generated_track.mid")
    score.write('midi', fp=output_filepath)
    
    # Write individual stems for Web DAW
    score_lead = stream.Score()
    score_lead.insert(0, part)
    if "lead" not in request.locked_stems:
        score_lead.write('midi', fp=os.path.join(os.path.dirname(__file__), "lead.mid"))
    
    if request.include_chords_bass:
        score_chords = stream.Score()
        score_chords.insert(0, chord_part)
        if "chords" not in request.locked_stems:
            score_chords.write('midi', fp=os.path.join(os.path.dirname(__file__), "chords.mid"))
        
        score_bass = stream.Score()
        score_bass.insert(0, bass_part)
        if "bass" not in request.locked_stems:
            score_bass.write('midi', fp=os.path.join(os.path.dirname(__file__), "bass.mid"))
        
    if request.include_drums:
        score_drums = stream.Score()
        score_drums.insert(0, drum_part)
        if "drums" not in request.locked_stems:
            score_drums.write('midi', fp=os.path.join(os.path.dirname(__file__), "drums.mid"))
    
    # Immediately render the audio using FluidSynth in PARALLEL
    base_dir = os.path.dirname(__file__)
    import platform
    if platform.system() == "Windows":
        fs_bin = os.path.join(base_dir, "synth", "bin", "fluidsynth.exe")
        sf2_path = os.path.join(base_dir, "synth", "soundfont.sf2")
    else:
        fs_bin = "fluidsynth"
        sf2_path = "/usr/share/sounds/sf2/FluidR3_GM.sf2"
    start_render = time.time()
    
    import shutil
    if shutil.which(fs_bin) and os.path.exists(sf2_path):
        import subprocess
        def render_stem(mid_name, wav_name):
            mid_path = os.path.join(base_dir, mid_name)
            wav_path = os.path.join(base_dir, wav_name)
            if not os.path.exists(mid_path): return None
            cmd = [
                fs_bin, "-ni", 
                "-o", "synth.gain=2.5",
                # Disabled backend Reverb/Chorus because the Web DAW handles effects locally using AudioContext!
                "-o", "synth.reverb.active=0", 
                "-o", "synth.chorus.active=0",
                sf2_path, mid_path, "-F", wav_path, "-r", "44100"
            ]
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        start_render = time.time()
        
        if "lead" not in request.locked_stems:
            print("Rendering Lead...")
            p_lead = render_stem("lead.mid", "lead.wav")
            if p_lead: p_lead.wait()
        
        if request.include_chords_bass:
            if "chords" not in request.locked_stems:
                print("Rendering Chords...")
                p_chords = render_stem("chords.mid", "chords.wav")
                if p_chords: p_chords.wait()
            
            if "bass" not in request.locked_stems:
                print("Rendering Bass...")
                p_bass = render_stem("bass.mid", "bass.wav")
                if p_bass: p_bass.wait()
            
        if request.include_drums:
            if "drums" not in request.locked_stems:
                print("Rendering Drums...")
                p_drums = render_stem("drums.mid", "drums.wav")
                if p_drums: p_drums.wait()
            
        end_render = time.time()
        print(f"FluidSynth Audio Rendering (Sequential) took {end_render - start_render:.2f} seconds.", flush=True)
    
    # Extract raw note data for the Piano Roll UI
    def extract_notes(p):
        notes_json = []
        if not p: return notes_json
        for el in p.recurse().notes:
            if isinstance(el, note.Note):
                notes_json.append({"pitch": el.pitch.midi, "offset": float(el.offset), "duration": float(el.quarterLength)})
            elif isinstance(el, chord.Chord):
                for p_obj in el.pitches:
                    notes_json.append({"pitch": p_obj.midi, "offset": float(el.offset), "duration": float(el.quarterLength)})
        return notes_json

    lead_notes_json = extract_notes(part)
    chords_notes_json = extract_notes(chord_part) if request.include_chords_bass else []
    bass_notes_json = extract_notes(bass_part) if request.include_chords_bass else []
    drums_notes_json = extract_notes(drum_part) if request.include_drums else []

    return {
        "status": "Success", 
        "message": "Multi-track generated successfully.", 
        "lead_notes": lead_notes_json,
        "chords_notes": chords_notes_json,
        "bass_notes": bass_notes_json,
        "drums_notes": drums_notes_json
    }

@app.get("/track")
async def get_track():
    output_filepath = os.path.join(os.path.dirname(__file__), "generated_track.mid")
    if os.path.exists(output_filepath):
        from fastapi.responses import FileResponse
        return FileResponse(output_filepath, media_type="audio/midi")
    return {"error": "Track not found"}

@app.post("/upload_stem_separation")
async def upload_stem_separation(file: UploadFile = File(...)):
    base_dir = os.path.dirname(__file__)
    temp_dir = os.path.join(base_dir, "temp_demucs")
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    print(f"File saved to {file_path}. Starting Demucs separation...", flush=True)
    
    try:
        out_dir = os.path.join(temp_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        
        # Call Demucs CLI module
        subprocess.run(["python", "-m", "demucs", "-o", out_dir, "-n", "htdemucs", file_path], check=True)
        
        basename = os.path.splitext(file.filename)[0]
        stems_dir = os.path.join(out_dir, "htdemucs", basename)
        
        # Map Demucs stems to NeuroComposer stems
        shutil.copy(os.path.join(stems_dir, "vocals.wav"), os.path.join(base_dir, "lead.wav"))
        shutil.copy(os.path.join(stems_dir, "bass.wav"), os.path.join(base_dir, "bass.wav"))
        shutil.copy(os.path.join(stems_dir, "drums.wav"), os.path.join(base_dir, "drums.wav"))
        shutil.copy(os.path.join(stems_dir, "other.wav"), os.path.join(base_dir, "chords.wav"))
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Detect BPM using librosa
        drums_path = os.path.join(base_dir, "drums.wav")
        detected_bpm = 120
        if os.path.exists(drums_path):
            try:
                print("Analyzing tempo...", flush=True)
                y, sr = librosa.load(drums_path, duration=30)
                bpm_val, _ = librosa.beat.beat_track(y=y, sr=sr)
                if isinstance(bpm_val, np.ndarray):
                    bpm_val = bpm_val[0]
                detected_bpm = int(round(float(bpm_val)))
                print(f"Detected BPM: {detected_bpm}", flush=True)
            except Exception as e:
                print(f"BPM Detection failed: {e}", flush=True)
        
        return {
            "status": "Success",
            "message": "Stem separation complete",
            "bpm": detected_bpm,
            "lead_notes": [],
            "chords_notes": [],
            "bass_notes": [],
            "drums_notes": []
        }
    except Exception as e:
        print(f"Demucs failed: {e}")
        return {"error": str(e)}

@app.get("/audio/{stem}")
async def get_audio_stem(stem: str):
    base_dir = os.path.dirname(__file__)
    valid_stems = ["master", "lead", "chords", "bass", "drums"]
    if stem not in valid_stems:
        return {"error": "Invalid stem requested."}
        
    wav_path = os.path.join(base_dir, f"{stem}.wav")
    if os.path.exists(wav_path):
        from fastapi.responses import FileResponse
        return FileResponse(wav_path, media_type="audio/wav", filename=f"NeuroComposer_{stem}.wav")
    return {"error": "Failed to locate audio stem."}







@app.get("/download_zip")
async def download_zip():
    import zipfile
    import io
    base_dir = os.path.dirname(__file__)
    files_to_zip = [
        "lead.wav", "lead.mid",
        "chords.wav", "chords.mid",
        "bass.wav", "bass.mid",
        "drums.wav", "drums.mid",
        "generated_track.mid"
    ]
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for f in files_to_zip:
            f_path = os.path.join(base_dir, f)
            if os.path.exists(f_path):
                zip_file.write(f_path, arcname=f"NeuroComposer_Project/{f}")
    
    zip_buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        zip_buffer, 
        media_type="application/x-zip-compressed", 
        headers={"Content-Disposition": "attachment; filename=NeuroComposer_Project.zip"}
    )

@app.get("/")
def read_root():
    return {"status": "NeuroComposer API is running!"}
