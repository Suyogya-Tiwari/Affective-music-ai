import os
import urllib.request

def download_file(url, save_path):
    try:
        print(f"Downloading {url}...")
        # Add a user agent to prevent 403 Forbidden on some servers
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(save_path, 'wb') as out_file:
            out_file.write(response.read())
        print(f"Saved to {save_path}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(base_dir, "raw_midi")
    
    happy_dir = os.path.join(raw_dir, "happy")
    sad_dir = os.path.join(raw_dir, "sad")
    
    os.makedirs(happy_dir, exist_ok=True)
    os.makedirs(sad_dir, exist_ok=True)
    
    # Happy Dataset (Mozart - typically upbeat, major key sonatas)
    happy_urls = [
        "http://www.piano-midi.de/midis/mozart/mz_330_1.mid",
        "http://www.piano-midi.de/midis/mozart/mz_330_2.mid",
        "http://www.piano-midi.de/midis/mozart/mz_330_3.mid",
        "http://www.piano-midi.de/midis/mozart/mz_311_1.mid",
        "http://www.piano-midi.de/midis/mozart/mz_311_2.mid"
    ]
    
    # Sad Dataset (Chopin - typically emotional, minor key preludes)
    sad_urls = [
        "http://www.piano-midi.de/midis/chopin/chpn-p1.mid",
        "http://www.piano-midi.de/midis/chopin/chpn-p2.mid",
        "http://www.piano-midi.de/midis/chopin/chpn-p3.mid",
        "http://www.piano-midi.de/midis/chopin/chpn-p4.mid",
        "http://www.piano-midi.de/midis/chopin/chpn-p6.mid"
    ]
    
    print("Downloading Happy Dataset (Mozart)...")
    for i, url in enumerate(happy_urls):
        save_path = os.path.join(happy_dir, f"mozart_{i+1}.mid")
        download_file(url, save_path)
        
    print("\nDownloading Sad Dataset (Chopin)...")
    for i, url in enumerate(sad_urls):
        save_path = os.path.join(sad_dir, f"chopin_{i+1}.mid")
        download_file(url, save_path)
        
    print("\nDataset download complete!")

if __name__ == "__main__":
    main()
