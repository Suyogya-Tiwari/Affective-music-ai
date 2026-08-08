import os
import subprocess
import zipfile
import shutil

def setup():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    synth_dir = os.path.join(base_dir, "synth")
    os.makedirs(synth_dir, exist_ok=True)
    
    fs_zip_path = os.path.join(synth_dir, "fluidsynth.zip")
    sf_zip_path = os.path.join(synth_dir, "soundfont.zip")
    sf_path = os.path.join(synth_dir, "soundfont.sf2")
    
    # Download FluidSynth
    if not os.path.exists(os.path.join(synth_dir, "fluidsynth-2.3.4-win10-x64", "bin", "fluidsynth.exe")):
        print("Downloading FluidSynth...")
        subprocess.run(["curl.exe", "-L", "-A", "Mozilla/5.0", "-o", fs_zip_path, "https://github.com/FluidSynth/fluidsynth/releases/download/v2.3.4/fluidsynth-2.3.4-win10-x64.zip"])
        print("Extracting FluidSynth...")
        try:
            with zipfile.ZipFile(fs_zip_path, 'r') as zip_ref:
                zip_ref.extractall(synth_dir)
            os.remove(fs_zip_path)
        except Exception as e:
            print("Failed to extract FluidSynth:", e)
    
    # Download VintageDreamsWaves-v2.sf2 directly to avoid 403 blocks
    if not os.path.exists(sf_path):
        print("Downloading Vintage SoundFont...")
        subprocess.run(["curl.exe", "-L", "-A", "Mozilla/5.0", "-o", sf_path, "https://github.com/FluidSynth/fluidsynth/raw/master/sf2/VintageDreamsWaves-v2.sf2"])
        
    print("Synthesizer environment setup is complete!")

if __name__ == "__main__":
    setup()
