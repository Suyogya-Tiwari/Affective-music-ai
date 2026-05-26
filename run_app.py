import os
import sys
import subprocess
import time
import webbrowser

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = os.path.join(base_dir, "venv", "Scripts", "python.exe")
    
    print("Starting NeuroComposer AI Backend...")
    
    # Start the backend server in a separate process
    server_process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "api.main:app", "--port", "8000"],
        cwd=base_dir
    )
    
    print("Waiting for the AI brain to load into memory (takes about 5-10 seconds)...")
    time.sleep(8)
    
    frontend_path = os.path.join(base_dir, "frontend", "index.html")
    print(f"Opening frontend interface at: {frontend_path}")
    
    # Open the frontend in the default web browser
    webbrowser.open(f"file://{frontend_path}")
    
    print("\n" + "="*50)
    print("SYSTEM IS LIVE!")
    print("Keep this terminal window open. Closing it will shut down the AI.")
    print("="*50 + "\n")
    
    try:
        # Keep the script running so the user sees the logs
        server_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down NeuroComposer...")
        server_process.terminate()

if __name__ == "__main__":
    main()
