document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('creativity-slider');
    const creativityInput = document.getElementById('creativity-input');
    const tempoSlider = document.getElementById('tempo-slider');
    const tempoInput = document.getElementById('tempo-input');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.getElementById('btn-text');
    const spinner = document.getElementById('loading-spinner');
    const midiPlayer = document.getElementById('my-player');

    // Sync creativity slider and input
    slider.addEventListener('input', (e) => {
        creativityInput.value = parseFloat(e.target.value).toFixed(1);
    });
    creativityInput.addEventListener('input', (e) => {
        let val = parseFloat(e.target.value);
        if(!isNaN(val)) slider.value = val;
    });

    // Sync tempo slider and input
    tempoSlider.addEventListener('input', (e) => {
        tempoInput.value = e.target.value;
    });
    tempoInput.addEventListener('input', (e) => {
        let val = parseInt(e.target.value);
        if(!isNaN(val)) tempoSlider.value = val;
    });

    // Handle Generation
    generateBtn.addEventListener('click', async () => {
        // Get Inputs
        const mood = document.querySelector('input[name="mood"]:checked').value;
        const creativity = slider.value;
        const tempo = tempoSlider.value;

        // UI Loading State
        generateBtn.disabled = true;
        btnText.textContent = "Composing...";
        spinner.classList.remove('hidden');

        // Determine the API URL based on where the frontend is hosted
        const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '';
        const API_BASE_URL = isLocalhost ? 'http://localhost:8000' : 'https://neurocomposer-api.onrender.com';

        try {
            // Fetch from backend
            const response = await fetch(`${API_BASE_URL}/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ mood: mood, creativity: parseFloat(creativity), tempo: parseInt(tempo) })
            });

            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            // Instead of dealing with browser blob policies, we tell the components to fetch the file natively!
            // Adding a timestamp prevents the browser from caching the old track
            const trackUrl = `${API_BASE_URL}/track?t=` + new Date().getTime();
            window.currentTrackUrl = trackUrl; // Save for download button
            
            const midiPlayer = document.getElementById('my-player');
            const visualizer = document.getElementById('my-visualizer');
            
            if (midiPlayer) midiPlayer.setAttribute('src', trackUrl);
            if (visualizer) visualizer.setAttribute('src', trackUrl);

            // Optional: Auto-play when ready
            // midiPlayer.start();

            btnText.textContent = "Track Generated!";
        } catch (error) {
            console.error("Error generating music:", error);
            btnText.textContent = "Error - Try Again";
        } finally {
            // Restore UI state
            generateBtn.disabled = false;
            spinner.classList.add('hidden');
            
            // Reset button text after 3 seconds if it was successful
            setTimeout(() => {
                if (btnText.textContent === "Track Generated!") {
                    btnText.textContent = "Generate Music";
                }
            }, 3000);
        }
    });

    // Handle DAW Download
    const downloadBtn = document.getElementById('download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            if (window.currentTrackUrl) {
                const a = document.createElement('a');
                a.href = window.currentTrackUrl;
                a.download = 'NeuroComposer_Track.mid';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            } else {
                alert("Please generate a track first!");
            }
        });
    }
});
