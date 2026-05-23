import os
import urllib.request
import zipfile
import shutil
from music21 import converter

def download_and_extract(url, extract_to):
    zip_path = os.path.join(extract_to, "maestro.zip")
    print("Downloading MAESTRO dataset (50MB)... This may take a minute.")
    
    # Download the file
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
        
    print("Download complete. Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    os.remove(zip_path)
    print("Extraction complete.")

def sort_midi_files(base_dir, max_files=20):
    raw_dir = os.path.join(base_dir, "raw_midi")
    happy_dir = os.path.join(raw_dir, "happy")
    sad_dir = os.path.join(raw_dir, "sad")
    
    # Clean old dummy data
    if os.path.exists(happy_dir):
        shutil.rmtree(happy_dir)
    if os.path.exists(sad_dir):
        shutil.rmtree(sad_dir)
        
    os.makedirs(happy_dir, exist_ok=True)
    os.makedirs(sad_dir, exist_ok=True)
    
    maestro_dir = os.path.join(base_dir, "maestro-v3.0.0")
    
    # Collect all midi files
    all_midis = []
    for root, dirs, files in os.walk(maestro_dir):
        for file in files:
            if file.endswith(".midi") or file.endswith(".mid"):
                all_midis.append(os.path.join(root, file))
                
    print(f"Found {len(all_midis)} MIDI files. Analyzing up to {max_files} files...")
    
    happy_count = 0
    sad_count = 0
    
    for file_path in all_midis:
        if happy_count + sad_count >= max_files:
            break
            
        try:
            # Load and analyze the key
            score = converter.parse(file_path)
            key = score.analyze('key')
            
            # MAESTRO files are huge. We only want files that parse successfully.
            # Copy to appropriate folder
            if key.mode == 'major':
                dest = os.path.join(happy_dir, f"song_{happy_count}.mid")
                shutil.copy2(file_path, dest)
                happy_count += 1
                print(f"[{happy_count + sad_count}/{max_files}] Detected Major Key -> Copied to Happy")
            elif key.mode == 'minor':
                dest = os.path.join(sad_dir, f"song_{sad_count}.mid")
                shutil.copy2(file_path, dest)
                sad_count += 1
                print(f"[{happy_count + sad_count}/{max_files}] Detected Minor Key -> Copied to Sad")
        except Exception as e:
            print(f"Skipping unparseable file: {e}")
            
    # Clean up the extracted massive MAESTRO folder to save space
    shutil.rmtree(maestro_dir)
    print(f"Sorting complete! Kept {happy_count} Happy songs and {sad_count} Sad songs.")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    url = "https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0-midi.zip"
    download_and_extract(url, base_dir)
    # Grab 20 songs to keep training time reasonable on CPU
    sort_midi_files(base_dir, max_files=20)

if __name__ == "__main__":
    main()
