import requests
import os
import time

os.makedirs('midi_exports', exist_ok=True)

emotions = ["happy", "sad", "energetic", "romantic", "dark", "dreamy"]
instruments = [
    (0, "Cinematic_Grand_Piano"),
    (4, "Vintage_Rhodes_Lounge"),
    (25, "Studio_Acoustic_Guitar"),
    (29, "Overdriven_Rock_Lead"),
    (40, "Solo_Chamber_Violin"),
    (48, "Lush_String_Ensemble"),
    (73, "Ethereal_Flute"),
    (89, "Warm_Synth_Pad")
]

print("Starting batch generation of 48 combinations...")

for mood in emotions:
    for inst_val, inst_name in instruments:
        filename = f"{mood}_{inst_name}.zip"
        if os.path.exists(f"midi_exports/{filename}"):
            print(f"Skipping {filename}, already exists.")
            continue
            
        print(f"Generating {mood} + {inst_name}...")
        payload = {
            "instrument": inst_val,
            "mood": mood,
            "creativity": 0.8,
            "chord_progression": "auto",
            "drum_groove": "auto",
            "arrangement": "band",
            "tempo": 120,
            "duration": 30, # We'll do 30 seconds
            "locked_stems": [],
            "seed_notes": []
        }
        
        try:
            # 1. Ask the AI to generate the track
            resp = requests.post("http://127.0.0.1:8080/generate", json=payload, timeout=60)
            if resp.status_code == 200:
                # 2. Download the resulting MIDI zip
                zip_resp = requests.get("http://127.0.0.1:8080/download_zip", timeout=10)
                if zip_resp.status_code == 200:
                    with open(f"midi_exports/{filename}", "wb") as f:
                        f.write(zip_resp.content)
                    print(f" -> Saved {filename} successfully!")
                else:
                    print(f" -> Failed to download zip: {zip_resp.status_code}")
            else:
                print(f" -> Failed generation: {resp.status_code}")
        except Exception as e:
            print(f" -> Error: {e}")
            
        # Give the server a larger breather to prevent memory crashes
        time.sleep(3)

print("\nBatch generation complete! All files saved to the 'midi_exports' directory.")
