# AI-Composer (NeuroComposer)

A full-stack web application that uses Machine Learning to generate music based on emotions.

This project allows users to select an emotion, and the AI backend will generate a unique piece of music that matches the mood.

## Features
- **Emotion-based Generation**: Choose from Happy, Sad, Energetic, Romantic, Dark, or Dreamy.
- **RESTful API Engine**: A Python FastAPI backend handles the heavy lifting of the Machine Learning model.
- **Interactive UI**: A Vanilla HTML/JS frontend where users can play back the generated audio.
- **Customization**: Users can select instruments and tempos to further guide the generation.

## How It Works
1. **Frontend**: The user makes a selection on the web interface.
2. **Backend**: The FastAPI server receives the request.
3. **AI Model**: A Neural Network predicts a sequence of musical notes that fit the selected emotion.
4. **Synthesis**: The Python backend uses FluidSynth to convert the raw notes into an audio file (.wav).
5. **Playback**: The frontend receives the audio file and plays it for the user.

## Running Locally

1. Create a virtual environment and install the requirements:
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

2. Run the application:
```bash
python scripts/run_app.py
```
This will start the local Python server and automatically open the interface in your web browser.
