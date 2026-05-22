document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('creativity-slider');
    const sliderValueDisplay = document.getElementById('slider-value');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.getElementById('btn-text');
    const spinner = document.getElementById('loading-spinner');
    const midiPlayer = document.getElementById('my-player');

    // Update creativity slider text in real-time
    slider.addEventListener('input', (e) => {
        sliderValueDisplay.textContent = parseFloat(e.target.value).toFixed(1);
    });

    // Handle Generation
    generateBtn.addEventListener('click', async () => {
        // Get Inputs
        const mood = document.querySelector('input[name="mood"]:checked').value;
        const creativity = slider.value;

        // UI Loading State
        generateBtn.disabled = true;
        btnText.textContent = "Composing...";
        spinner.classList.remove('hidden');

        try {
            // Fetch from backend
            const response = await fetch(`http://localhost:8000/generate?mood=${mood}&creativity=${creativity}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            // Get MIDI blob
            const blob = await response.blob();
            
            // Create a local URL for the blob
            const midiUrl = URL.createObjectURL(blob);
            
            // Pass the URL to the magenta html-midi-player
            midiPlayer.src = midiUrl;

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
});
