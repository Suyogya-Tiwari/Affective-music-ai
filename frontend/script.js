let currentEmotion = "happy"; // default
let synth = null;
let recordedNotes = [];

document.addEventListener('DOMContentLoaded', () => {
    // Unified DAW Interface Initialization
    // The Studio Mixer is now always visible on the right.

    // Initialize Tone.js synth on first user interaction
    document.body.addEventListener('click', () => {
        if (!synth) {
            synth = new Tone.PolySynth(Tone.Synth).toDestination();
            synth.volume.value = -8;
        }
    }, { once: true });

    // Virtual Piano Logic
    const seedInput = document.getElementById('seed-notes-input');
    const virtualKeys = document.querySelectorAll('.virtual-piano .key');
    const clearBtn = document.getElementById('clear-seed');
    
    // Map note names to MIDI pitches for the Piano Roll visualization
    const noteToMidi = { "C4":60, "C#4":61, "D4":62, "D#4":63, "E4":64, "F4":65, "F#4":66, "G4":67, "G#4":68, "A4":69, "A#4":70, "B4":71, "C5":72 };

    virtualKeys.forEach(key => {
        key.addEventListener('mousedown', () => {
            const note = key.getAttribute('data-note');
            if (synth) synth.triggerAttackRelease(note, "8n");
            
            recordedNotes.push(note);
            seedInput.value = recordedNotes.join(", ");
            
            // Visual feedback
            const originalBg = key.style.background;
            key.style.background = 'var(--gold-400)';
            setTimeout(() => {
                key.style.background = originalBg;
            }, 150);
            
            // Draw primer sequence on the Piano Roll!
            const primerNotes = recordedNotes.map((n, i) => ({
                pitch: noteToMidi[n] || 60,
                offset: i * 0.5, // assumed 8th note spacing
                duration: 0.5
            }));
            
            // Temporarily switch to Studio tab to show the drawing
            const studioTabBtn = document.querySelector('[data-target="tab-copilot"]');
            if (studioTabBtn && !studioTabBtn.classList.contains('active')) {
                studioTabBtn.click();
            }
            
            masterBuffer = null; // Clear old master
            lastGeneratedData = primerNotes;
            drawPianoRoll(primerNotes);
        });
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            recordedNotes = [];
            seedInput.value = "";
            drawPianoRoll([]); // Clear canvas
        });
    }

    const slider = document.getElementById('creativity-slider');
    const creativityInput = document.getElementById('creativity-input');
    const tempoSlider = document.getElementById('tempo-slider');
    const tempoInput = document.getElementById('tempo-input');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.getElementById('btn-text');
    const spinner = document.getElementById('loading-waveform');

    // Sync sliders
    slider.addEventListener('input', (e) => {
        creativityInput.value = parseFloat(e.target.value).toFixed(1);
    });
    creativityInput.addEventListener('input', (e) => {
        let val = parseFloat(e.target.value);
        if(!isNaN(val)) slider.value = val;
    });

    let userTouchedTempo = false;

    tempoSlider.addEventListener('input', (e) => {
        tempoInput.value = e.target.value;
        userTouchedTempo = true;
    });
    tempoInput.addEventListener('input', (e) => {
        let val = parseInt(e.target.value);
        if(!isNaN(val)) tempoSlider.value = val;
        userTouchedTempo = true;
    });
    
    // Auto-update BPM on emotion select
    const moodRadios = document.querySelectorAll('input[name="mood"]');
    const defaultBpms = {
        "sad": 75,
        "romantic": 85,
        "dreamy": 90,
        "dark": 105,
        "happy": 120,
        "energetic": 130
    };
    
    moodRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (!userTouchedTempo) {
                const newBpm = defaultBpms[e.target.value];
                if (newBpm) {
                    tempoSlider.value = newBpm;
                    tempoInput.value = newBpm;
                }
            }
        });
    });

    // Handle Generation
    generateBtn.addEventListener('click', async () => {
        const moodInput = document.querySelector('input[name="mood"]:checked');
        const mood = moodInput ? moodInput.value : "happy";
        const tempo = document.getElementById('tempo-slider').value;
        const creativity = document.getElementById('creativity-slider').value;
        const duration = document.getElementById('duration').value;
        const instrumentId = document.getElementById('instrument-select').value;
        const arrangementInput = document.querySelector('input[name="arrangement"]:checked');
        const arrangement = arrangementInput ? arrangementInput.value : "solo";
        const includeDrums = (arrangement === "drums" || arrangement === "band");
        const includeChordsBass = (arrangement === "band");
        const chordProgression = document.getElementById('chord-progression').value;
        const drumGroove = document.getElementById('drum-groove').value;

        generateBtn.disabled = true;
        btnText.textContent = "Composing...";
        spinner.classList.remove('hidden');

        // Always use the local backend server that we just optimized with the JIT compiler!
        const API_BASE_URL = 'http://127.0.0.1:8080';
        
        const lockedArray = [];
        document.querySelectorAll('.lock-btn').forEach(btn => {
            if (btn.dataset.locked === 'true') {
                lockedArray.push(btn.dataset.stem);
            }
        });

        try {
            const response = await fetch(`${API_BASE_URL}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    mood: mood,
                    creativity: parseFloat(creativity),
                    tempo: parseInt(tempo),
                    duration: parseInt(duration),
                    instrument: parseInt(instrumentId),
                    include_drums: includeDrums,
                    include_chords_bass: includeChordsBass,
                    chord_progression: chordProgression,
                    drum_groove: drumGroove,
                    seed_notes: recordedNotes,
                    locked_stems: lockedArray
                })
            });

            if (!response.ok) throw new Error(`Server responded with ${response.status}`);

            if (response.ok) {
                const data = await response.json();
                
                // Automatically switch to the Studio tab so the user sees the DAW
                const studioTabBtn = document.querySelector('[data-target="tab-copilot"]');
                if (studioTabBtn) studioTabBtn.click();

                masterBuffer = null;
                lastGeneratedData = data;
                drawPianoRoll(data);

                // Initialize Web DAW
                await initWebDAW(API_BASE_URL, includeChordsBass, includeDrums);
            }

            btnText.textContent = "Track Generated!";
        } catch (error) {
            console.error("Error generating music:", error);
            btnText.textContent = "Error - Try Again";
        } finally {
            generateBtn.disabled = false;
            spinner.classList.add('hidden');
            setTimeout(() => {
                if (btnText.textContent === "Track Generated!" || btnText.textContent === "Error - Try Again") {
                    btnText.textContent = "Generate Track";
                }
            }, 3000);
        }
    });

    // Handle Remix Upload

    // Handle Voice-to-MIDI Melody Seed
    const humInput = document.getElementById('hum-upload-input');
    const dropzone = document.getElementById('seed-dropzone');
    const dropzoneText = document.getElementById('dropzone-text');
    const recordBtn = document.getElementById('record-mic-btn');
    const recordText = document.getElementById('record-text');
    const recordIcon = document.getElementById('record-icon');
    
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    
    async function processSeedAudio(fileOrBlob) {
        if (!fileOrBlob) return;
        
        const originalText = dropzoneText.innerHTML;
        dropzoneText.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        dropzone.style.pointerEvents = 'none';
        
        const API_BASE_URL = 'http://127.0.0.1:8080';
        const formData = new FormData();
        formData.append('file', fileOrBlob, fileOrBlob.name || 'recorded_hum.webm');
        
        try {
            const response = await fetch(`${API_BASE_URL}/upload_audio_seed`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) throw new Error(`Server responded with ${response.status}`);
            
            const data = await response.json();
            
            if (data.notes && data.notes.length > 0) {
                recordedNotes = data.notes;
                
                document.querySelectorAll('.key').forEach(k => {
                    k.classList.remove('active');
                    k.style.boxShadow = "none";
                });
                
                recordedNotes.forEach(note => {
                    const key = document.querySelector(`.key[data-note="${note}"]`);
                    if (key) {
                        key.classList.add('active');
                        key.style.boxShadow = "0 0 15px var(--gold-500)";
                        setTimeout(() => {
                            key.style.boxShadow = "none";
                        }, 3000);
                    }
                });
                
                dropzoneText.innerHTML = '<span style="color: var(--gold-400);"><i class="fas fa-check"></i> Notes Extracted!</span>';
            } else {
                dropzoneText.innerHTML = '<span style="color: #f87171;"><i class="fas fa-times"></i> No Pitch Detected</span>';
            }
        } catch (err) {
            console.error("Error extracting pitch:", err);
            dropzoneText.innerHTML = '<span style="color: #f87171;"><i class="fas fa-exclamation-triangle"></i> Error Processing</span>';
        } finally {
            setTimeout(() => {
                dropzoneText.innerHTML = originalText;
                dropzone.style.pointerEvents = 'auto';
            }, 3000);
        }
    }
    
    if (dropzone && humInput) {
        dropzone.addEventListener('click', () => humInput.click());
        
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.style.backgroundColor = 'rgba(202, 138, 4, 0.2)';
            dropzone.style.borderColor = 'var(--gold-400)';
        });
        
        ['dragleave', 'dragend'].forEach(type => {
            dropzone.addEventListener(type, (e) => {
                e.preventDefault();
                dropzone.style.backgroundColor = 'rgba(202, 138, 4, 0.05)';
                dropzone.style.borderColor = 'var(--gold-600)';
            });
        });
        
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.style.backgroundColor = 'rgba(202, 138, 4, 0.05)';
            dropzone.style.borderColor = 'var(--gold-600)';
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                processSeedAudio(e.dataTransfer.files[0]);
            }
        });
        
        humInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                processSeedAudio(e.target.files[0]);
            }
        });
    }

    if (recordBtn) {
        recordBtn.addEventListener('click', async () => {
            if (isRecording) {
                mediaRecorder.stop();
                isRecording = false;
                recordText.textContent = "Record";
                recordBtn.style.background = "rgba(220, 38, 38, 0.2)";
                recordIcon.classList.remove('fa-beat-fade');
                return;
            }
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = e => {
                    if (e.data.size > 0) audioChunks.push(e.data);
                };
                
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    stream.getTracks().forEach(track => track.stop());
                    processSeedAudio(audioBlob);
                };
                
                mediaRecorder.start();
                isRecording = true;
                
                recordText.textContent = "Stop";
                recordBtn.style.background = "rgba(220, 38, 38, 0.4)";
                recordIcon.classList.add('fa-beat-fade');
                
                setTimeout(() => {
                    if (isRecording) recordBtn.click();
                }, 5000);
                
            } catch (err) {
                console.error("Microphone access denied or error:", err);
                alert("Microphone access is required to record a melody seed.");
            }
        });
    }

    // --- PIANO ROLL SEQUENCER ---
    function drawPianoRoll(data) {
        const canvas = document.getElementById('piano-roll-canvas');
        if (!canvas) return;
        
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
        const ctx = canvas.getContext('2d');
        
        let allNotes = [];
        if (data.lead_notes) allNotes = allNotes.concat(data.lead_notes);
        if (data.chords_notes) allNotes = allNotes.concat(data.chords_notes);
        if (data.bass_notes) allNotes = allNotes.concat(data.bass_notes);
        if (data.drums_notes) allNotes = allNotes.concat(data.drums_notes);
        
        if (allNotes.length === 0) return;
        
        let minPitch = 127, maxPitch = 0, maxTime = 0;
        allNotes.forEach(n => {
            if (n.pitch < minPitch) minPitch = n.pitch;
            if (n.pitch > maxPitch) maxPitch = n.pitch;
            if (n.offset + n.duration > maxTime) maxTime = n.offset + n.duration;
        });
        
        minPitch -= 3;
        maxPitch += 3;
        const pitchRange = maxPitch - minPitch;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // --- DRAW MASTER WAVEFORM BACKGROUND (IF EXISTS) ---
        if (masterBuffer) {
            const rawData = masterBuffer.getChannelData(0);
            const step = Math.ceil(rawData.length / canvas.width);
            const amp = canvas.height / 2;
            
            ctx.fillStyle = 'rgba(255, 255, 255, 0.2)'; // Transparent white waveform
            for (let i = 0; i < canvas.width; i++) {
                let min = 1.0;
                let max = -1.0;
                for (let j = 0; j < step; j++) {
                    const datum = rawData[(i * step) + j]; 
                    if (datum < min) min = datum;
                    if (datum > max) max = datum;
                }
                const y = (1 + min) * amp;
                const h = Math.max(1, (max - min) * amp);
                ctx.fillRect(i, y, 1, h);
            }
        }
        
        // Grid lines
        ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        ctx.lineWidth = 1;
        for (let i = 0; i <= maxTime; i++) {
            const x = (i / maxTime) * canvas.width;
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
            if (i % 4 === 0) {
                ctx.fillStyle = 'rgba(255,255,255,0.2)';
                ctx.font = '10px Inter';
                ctx.fillText(`Bar ${i/4 + 1}`, x + 5, 15);
            }
        }
        
        // Pitch lines
        for (let p = minPitch; p <= maxPitch; p++) {
            const y = canvas.height - (((p - minPitch) / pitchRange) * canvas.height);
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
        }
        
        // Draw Notes Helper
        function drawNoteArray(notes, color1, color2, isDrum=false) {
            if (!notes) return;
            notes.forEach(n => {
                const x = (n.offset / maxTime) * canvas.width;
                const w = Math.max((n.duration / maxTime) * canvas.width, 2); // Minimum width of 2px
                
                let y, h;
                if (isDrum) {
                    y = canvas.height - 10; // Draw drums at the very bottom
                    h = 6; // Fixed height for drum hits
                } else {
                    y = canvas.height - (((n.pitch - minPitch) / pitchRange) * canvas.height);
                    h = Math.max(canvas.height / pitchRange, 4);
                }
                
                const grad = ctx.createLinearGradient(x, y, x, y + h);
                grad.addColorStop(0, color1);
                grad.addColorStop(1, color2);
                
                ctx.fillStyle = grad;
                ctx.fillRect(x, y, w, h);
                
                ctx.strokeStyle = 'rgba(0,0,0,0.5)';
                ctx.lineWidth = 1;
                ctx.strokeRect(x, y, w, h);
            });
        }
        
        // Draw all tracks
        drawNoteArray(data.chords_notes, 'rgba(56, 189, 248, 0.6)', 'rgba(2, 132, 199, 0.8)'); // Blue Chords (Background)
        drawNoteArray(data.bass_notes, 'rgba(192, 132, 252, 0.8)', 'rgba(147, 51, 234, 1)'); // Purple Bass
        drawNoteArray(data.drums_notes, 'rgba(248, 113, 113, 1)', 'rgba(220, 38, 38, 1)', true); // Red Drums
        drawNoteArray(data.lead_notes, 'rgba(250, 204, 21, 1)', 'rgba(202, 138, 4, 1)'); // Gold Lead (Foreground)
    }

    // --- WEB DAW ENGINE ---
    let audioCtx = null;
    let analyser = null;
    let masterGain = null;
    let masterDelay = null;
    let masterDelayGain = null;
    let masterDelayWet = null;
    let masterDistortion = null;
    let masterCompressor = null;
    let eqLow = null;
    let eqMid = null;
    let eqHigh = null;
    let stemBuffers = {};
    let stemSources = {};
    let stemGains = {};
    let isPlaying = false;
    let animationId = null;
    let startTime = 0;
    let timerInterval = null;
    let maxDuration = 0;
    let pauseOffset = 0;
    let isDraggingSeek = false;
    let loopStart = 0;
    let loopEnd = 0;
    let isLooping = false;
    let masterBuffer = null;
    let lastGeneratedData = null;
    
    function formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return "00:00";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    
    function updateTimer() {
        if (!audioCtx || !isPlaying) return;
        if (isDraggingSeek) return; // Don't snap back while user is sliding
        
        let elapsed = audioCtx.currentTime - startTime;
        
        if (isLooping && loopEnd > loopStart) {
            const loopDuration = loopEnd - loopStart;
            if (elapsed >= loopEnd) {
                elapsed = loopStart + ((elapsed - loopEnd) % loopDuration);
            }
        }
        
        if (!isLooping && elapsed > maxDuration) {
            elapsed = maxDuration;
            stopAll(true); // reset to 0 at the end
            return;
        }
        
        const timerEl = document.getElementById('playback-timer');
        if (timerEl) {
            timerEl.textContent = `${formatTime(elapsed)} / ${formatTime(maxDuration)}`;
        }
        
        const slider = document.getElementById('seek-slider');
        if (slider && maxDuration > 0) {
            slider.value = (elapsed / maxDuration) * 100;
        }
    }

    function makeDistortionCurve(amount) {
        const k = amount * 100, n_samples = 44100, curve = new Float32Array(n_samples), deg = Math.PI / 180;
        for (let i = 0; i < n_samples; ++i) {
            let x = i * 2 / n_samples - 1;
            curve[i] = (3 + k) * x * 20 * deg / (Math.PI + k * Math.abs(x));
        }
        return curve;
    }

    async function initWebDAW(API_BASE_URL, hasChordsBass, hasDrums) {
        if (audioCtx) {
            await audioCtx.close();
            cancelAnimationFrame(animationId);
        }
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        masterGain = audioCtx.createGain();
        
        // Master FX (Delay, Distortion, EQ, Compressor)
        masterDelay = audioCtx.createDelay(5.0);
        masterDelayGain = audioCtx.createGain(); // Feedback
        masterDelayWet = audioCtx.createGain();
        masterDistortion = audioCtx.createWaveShaper();
        masterCompressor = audioCtx.createDynamicsCompressor();
        
        eqLow = audioCtx.createBiquadFilter();
        eqLow.type = 'lowshelf';
        eqLow.frequency.value = 300;
        
        eqMid = audioCtx.createBiquadFilter();
        eqMid.type = 'peaking';
        eqMid.frequency.value = 1000;
        eqMid.Q.value = 1;
        
        eqHigh = audioCtx.createBiquadFilter();
        eqHigh.type = 'highshelf';
        eqHigh.frequency.value = 4000;
        masterDistortion.curve = makeDistortionCurve(0);
        masterDistortion.oversample = '4x';
        
        // Routing Chain: Gain -> EQ Low -> EQ Mid -> EQ High -> Distortion -> Compressor -> Analyser -> Dest
        masterGain.connect(eqLow);
        eqLow.connect(eqMid);
        eqMid.connect(eqHigh);
        eqHigh.connect(masterDistortion);
        masterDistortion.connect(masterCompressor);
        masterCompressor.connect(analyser);
        
        // Delay (Parallel routing from masterGain)
        masterDelay.delayTime.value = 0.33; // ~1/8th note delay
        masterGain.connect(masterDelay);
        masterDelay.connect(masterDelayGain);
        masterDelayGain.connect(masterDelay); // Feedback loop
        masterDelay.connect(masterDelayWet);
        masterDelayWet.connect(analyser);
        
        masterDelayGain.gain.value = 0.4;
        masterDelayWet.gain.value = 0;
        
        // Default Compressor settings
        masterCompressor.threshold.value = 0; // inactive by default
        masterCompressor.knee.value = 40;
        masterCompressor.ratio.value = 1; // 1:1 (no compression)
        masterCompressor.attack.value = 0;
        masterCompressor.release.value = 0.25;
        
        analyser.connect(audioCtx.destination);
        
        // Bind UI Sliders
        const compSlider = document.getElementById('master-comp');
        if (compSlider) compSlider.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value); // 0 to 1
            masterCompressor.threshold.value = -50 * val; // down to -50dB
            masterCompressor.ratio.value = 1 + (19 * val); // up to 20:1
        });
        
        const eqLowSlider = document.getElementById('master-eq-low');
        if (eqLowSlider) eqLowSlider.addEventListener('input', (e) => eqLow.gain.value = parseFloat(e.target.value));
        
        const eqMidSlider = document.getElementById('master-eq-mid');
        if (eqMidSlider) eqMidSlider.addEventListener('input', (e) => eqMid.gain.value = parseFloat(e.target.value));
        
        const eqHighSlider = document.getElementById('master-eq-high');
        if (eqHighSlider) eqHighSlider.addEventListener('input', (e) => eqHigh.gain.value = parseFloat(e.target.value));
        
        const delaySlider = document.getElementById('master-delay');
        if (delaySlider) delaySlider.addEventListener('input', (e) => masterDelayWet.gain.value = parseFloat(e.target.value));
        
        const distSlider = document.getElementById('master-distortion');
        if (distSlider) distSlider.addEventListener('input', (e) => masterDistortion.curve = makeDistortionCurve(parseFloat(e.target.value) / 100));


        const stemsToLoad = ['lead'];
        if (hasChordsBass) { stemsToLoad.push('chords', 'bass'); }
        if (hasDrums) { stemsToLoad.push('drums'); }

        stemBuffers = {};
        btnText.textContent = "Loading Stems...";

        const t = new Date().getTime();
        await Promise.all(stemsToLoad.map(async (stem) => {
            try {
                const res = await fetch(`${API_BASE_URL}/audio/${stem}?t=${t}`);
                if (!res.ok) throw new Error("Stem missing");
                const arrayBuffer = await res.arrayBuffer();
                stemBuffers[stem] = await audioCtx.decodeAudioData(arrayBuffer);
            } catch(e) {
                console.error(`Failed to load ${stem}`, e);
            }
        }));

        setupMixer();
        drawVisualizer();
        btnText.textContent = "Track Generated!";
        
        maxDuration = 0;
        Object.keys(stemBuffers).forEach(s => {
            if (stemBuffers[s] && stemBuffers[s].duration > maxDuration) {
                maxDuration = stemBuffers[s].duration;
            }
        });
        const timerEl = document.getElementById('playback-timer');
        if (timerEl) {
            timerEl.textContent = `00:00 / ${formatTime(maxDuration)}`;
        }
        const topBar = document.getElementById('transport-top-bar');
        if (topBar) topBar.classList.remove('hidden');
    }

    function createReverbIR(audioCtx) {
        const length = audioCtx.sampleRate * 2.5; 
        const impulse = audioCtx.createBuffer(2, length, audioCtx.sampleRate);
        for (let i = 0; i < 2; i++) {
            const channel = impulse.getChannelData(i);
            for (let j = 0; j < length; j++) {
                channel[j] = (Math.random() * 2 - 1) * Math.pow(1 - j / length, 3);
            }
        }
        return impulse;
    }

    function setupMixer() {
        const stems = ['lead', 'chords', 'bass', 'drums'];
        stems.forEach(stem => {
            const fader = document.getElementById(`vol-${stem}`);
            const muteBtn = document.getElementById(`mute-${stem}`);
            const revFader = document.getElementById(`rev-${stem}`);
            const lpfFader = document.getElementById(`lpf-${stem}`);
            
            const delFader = document.getElementById(`del-${stem}`);
            const distFader = document.getElementById(`dist-${stem}`);
            
            if (!stemGains[stem]) {
                const master = audioCtx.createGain();
                const filter = audioCtx.createBiquadFilter();
                const dist = audioCtx.createWaveShaper();
                const delay = audioCtx.createDelay(5.0);
                const delayGain = audioCtx.createGain();
                const delayWet = audioCtx.createGain();
                const wet = audioCtx.createGain();
                const dry = audioCtx.createGain();
                const convolver = audioCtx.createConvolver();
                
                filter.type = 'lowpass';
                filter.frequency.value = 10000;
                dist.curve = makeDistortionCurve(0);
                dist.oversample = '4x';
                
                delay.delayTime.value = 0.33;
                delayGain.gain.value = 0.4;
                delayWet.gain.value = 0;
                
                convolver.buffer = createReverbIR(audioCtx);
                
                // Route: Filter -> Dist -> Master (Dry) & Reverb
                filter.connect(dist);
                
                // Dist to Delay
                dist.connect(delay);
                delay.connect(delayGain);
                delayGain.connect(delay);
                delay.connect(delayWet);
                
                // Dry + Delay -> Reverb & Master
                dist.connect(dry);
                delayWet.connect(dry);
                
                dist.connect(convolver);
                delayWet.connect(convolver);
                
                convolver.connect(wet);
                dry.connect(master);
                wet.connect(master);
                master.connect(masterGain);
                
                wet.gain.value = 0.2;
                dry.gain.value = 0.8;
                
                stemGains[stem] = { master, filter, wet, dry, dist, delayWet };
            }
            
            if (fader && muteBtn) {
                fader.addEventListener('input', (e) => {
                    if (muteBtn.dataset.state === 'on') {
                        stemGains[stem].master.gain.value = parseFloat(e.target.value);
                    }
                });
                
                if (revFader) {
                    revFader.addEventListener('input', (e) => {
                        const val = parseFloat(e.target.value);
                        stemGains[stem].wet.gain.value = val;
                        stemGains[stem].dry.gain.value = 1 - val;
                    });
                }
                
                if (lpfFader) {
                    lpfFader.addEventListener('input', (e) => {
                        stemGains[stem].filter.frequency.value = parseFloat(e.target.value);
                    });
                }
                
                if (delFader) {
                    delFader.addEventListener('input', (e) => {
                        stemGains[stem].delayWet.gain.value = parseFloat(e.target.value);
                    });
                }
                
                if (distFader) {
                    distFader.addEventListener('input', (e) => {
                        stemGains[stem].dist.curve = makeDistortionCurve(parseFloat(e.target.value) / 100);
                    });
                }
                
                // Remove old listeners to prevent stacking
                const newMuteBtn = muteBtn.cloneNode(true);
                muteBtn.parentNode.replaceChild(newMuteBtn, muteBtn);
                
                newMuteBtn.addEventListener('click', () => {
                    if (newMuteBtn.dataset.state === 'on') {
                        newMuteBtn.dataset.state = 'muted';
                        newMuteBtn.style.background = 'var(--slate-700)';
                        newMuteBtn.style.color = 'var(--slate-300)';
                        newMuteBtn.textContent = 'M';
                        stemGains[stem].master.gain.value = 0;
                    } else {
                        newMuteBtn.dataset.state = 'on';
                        newMuteBtn.style.background = 'var(--gold-600)';
                        newMuteBtn.style.color = 'var(--bg-base)';
                        newMuteBtn.textContent = 'ON';
                        stemGains[stem].master.gain.value = fader ? parseFloat(fader.value) : 1;
                    }
                });
            }
        });
    }

    function playAll() {
        if (!audioCtx) return;
        
        const currentOffset = pauseOffset; // save offset
        stopAll(false); // Stop currently playing nodes without resetting offset
        
        const stems = Object.keys(stemBuffers);
        stems.forEach(stem => {
            if (stemBuffers[stem]) {
                const source = audioCtx.createBufferSource();
                source.buffer = stemBuffers[stem];
                
                if (isLooping) {
                    source.loop = true;
                    source.loopStart = loopStart;
                    source.loopEnd = loopEnd > loopStart ? loopEnd : maxDuration;
                }
                
                source.connect(stemGains[stem].filter);
                source.start(0, currentOffset);
                stemSources[stem] = source;
                
                // sync fader initially
                const fader = document.getElementById(`vol-${stem}`);
                const muteBtn = document.getElementById(`mute-${stem}`);
                const revFader = document.getElementById(`rev-${stem}`);
                const lpfFader = document.getElementById(`lpf-${stem}`);
                
                const delFader = document.getElementById(`del-${stem}`);
                const distFader = document.getElementById(`dist-${stem}`);
                
                if (muteBtn && muteBtn.dataset.state === 'on') {
                    stemGains[stem].master.gain.value = fader ? parseFloat(fader.value) : 1;
                } else {
                    stemGains[stem].master.gain.value = 0;
                }
                
                if (revFader) {
                    stemGains[stem].wet.gain.value = parseFloat(revFader.value);
                    stemGains[stem].dry.gain.value = 1 - parseFloat(revFader.value);
                }
                
                if (lpfFader) {
                    stemGains[stem].filter.frequency.value = parseFloat(lpfFader.value);
                }
                
                if (delFader) {
                    stemGains[stem].delayWet.gain.value = parseFloat(delFader.value);
                }
                
                if (distFader) {
                    stemGains[stem].dist.curve = makeDistortionCurve(parseFloat(distFader.value) / 100);
                }
            }
        });
        isPlaying = true;
        startTime = audioCtx.currentTime - currentOffset;
        pauseOffset = currentOffset; // restore global
        
        if (timerInterval) clearInterval(timerInterval);
        timerInterval = setInterval(updateTimer, 50); // fast UI updates for the scrubber
    }

    function stopAll(resetOffset = true) {
        if (!audioCtx) return;
        const stems = Object.keys(stemSources);
        stems.forEach(stem => {
            if (stemSources[stem]) {
                try { stemSources[stem].stop(); } catch(e){}
            }
        });
        stemSources = {};
        
        const wasPlaying = isPlaying;
        isPlaying = false;
        
        if (resetOffset) {
            pauseOffset = 0;
            const timerEl = document.getElementById('playback-timer');
            if (timerEl) timerEl.textContent = `00:00 / ${formatTime(maxDuration)}`;
            const slider = document.getElementById('seek-slider');
            if (slider) slider.value = 0;
        } else if (wasPlaying) {
            // we are pausing/seeking while active
            pauseOffset = audioCtx.currentTime - startTime;
        }
        
        if (timerInterval) clearInterval(timerInterval);
    }

    document.getElementById('daw-play-btn')?.addEventListener('click', () => playAll());
    document.getElementById('daw-stop-btn')?.addEventListener('click', () => stopAll(true));

    const seekSlider = document.getElementById('seek-slider');
    if (seekSlider) {
        seekSlider.addEventListener('mousedown', () => {
            isDraggingSeek = true;
        });
        seekSlider.addEventListener('input', (e) => {
            if (!maxDuration) return;
            const percent = e.target.value / 100;
            pauseOffset = percent * maxDuration;
            const timerEl = document.getElementById('playback-timer');
            if (timerEl) {
                timerEl.textContent = `${formatTime(pauseOffset)} / ${formatTime(maxDuration)}`;
            }
        });
        seekSlider.addEventListener('mouseup', (e) => {
            isDraggingSeek = false;
            if (!maxDuration) return;
            const percent = e.target.value / 100;
            pauseOffset = percent * maxDuration;
            if (isPlaying) {
                stopAll(false);
                playAll();
            }
        });
    }

    // A/B Looping Controls
    const loopToggleBtn = document.getElementById('loop-toggle-btn');
    const loopInBtn = document.getElementById('loop-in-btn');
    const loopOutBtn = document.getElementById('loop-out-btn');

    if (loopToggleBtn) {
        loopToggleBtn.addEventListener('click', () => {
            isLooping = !isLooping;
            loopToggleBtn.textContent = isLooping ? 'LOOP: ON' : 'LOOP: OFF';
            loopToggleBtn.style.color = isLooping ? 'var(--gold-400)' : 'var(--slate-400)';
            loopToggleBtn.style.borderColor = isLooping ? 'var(--gold-400)' : 'var(--slate-400)';
            if (isPlaying) {
                stopAll(false);
                playAll(); // Restart to apply loop settings
            }
        });
    }

    if (loopInBtn) {
        loopInBtn.addEventListener('click', () => {
            if (!audioCtx) return;
            let elapsed = isPlaying ? audioCtx.currentTime - startTime : pauseOffset;
            loopStart = elapsed;
            loopInBtn.style.background = 'rgba(250, 204, 21, 0.3)';
            setTimeout(() => loopInBtn.style.background = 'rgba(255,255,255,0.1)', 200);
            if (isPlaying && isLooping) {
                stopAll(false);
                playAll();
            }
        });
    }

    if (loopOutBtn) {
        loopOutBtn.addEventListener('click', () => {
            if (!audioCtx) return;
            let elapsed = isPlaying ? audioCtx.currentTime - startTime : pauseOffset;
            loopEnd = elapsed;
            loopOutBtn.style.background = 'rgba(250, 204, 21, 0.3)';
            setTimeout(() => loopOutBtn.style.background = 'rgba(255,255,255,0.1)', 200);
            
            // Auto-enable loop if both points are set
            if (!isLooping && loopEnd > loopStart) {
                loopToggleBtn.click();
            }
            if (isPlaying && isLooping) {
                stopAll(false);
                playAll();
            }
        });
    }

    // Stem Locking Toggles (Hybrid Mode)
    document.querySelectorAll('.lock-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const isLocked = btn.dataset.locked === 'true';
            if (isLocked) {
                btn.dataset.locked = 'false';
                btn.style.opacity = '0.5';
                btn.style.color = 'var(--white)';
                btn.textContent = '🔓';
            } else {
                btn.dataset.locked = 'true';
                btn.style.opacity = '1.0';
                btn.style.color = 'var(--gold-400)';
                btn.textContent = '🔒';
            }
        });
    });

    // Canvas Visualizer
    function drawVisualizer() {
        if (!analyser) return;
        const canvas = document.getElementById('master-visualizer');
        if (!canvas) return;
        const canvasCtx = canvas.getContext('2d');
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        
        canvasCtx.clearRect(0, 0, canvas.width, canvas.height);

        function draw() {
            animationId = requestAnimationFrame(draw);
            analyser.getByteFrequencyData(dataArray);
            
            canvasCtx.fillStyle = 'rgba(0, 0, 0, 0.2)';
            canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
            
            const barWidth = (canvas.width / bufferLength) * 2.5;
            let barHeight;
            let x = 0;
            
            const time = Date.now() * 0.002; // for idle animation
            
            for(let i = 0; i < bufferLength; i++) {
                barHeight = dataArray[i];
                
                // If not playing, draw a beautiful idle sine-wave pulse
                if (!isPlaying && barHeight === 0) {
                    barHeight = 5 + Math.sin(time + i * 0.1) * 3;
                } else if (barHeight === 0) {
                    barHeight = 2; // Flat baseline when playing silence
                }
                
                // Gold glowing bars
                canvasCtx.fillStyle = `rgb(${barHeight + 50}, ${barHeight > 100 ? 204 : 100}, 21)`;
                canvasCtx.fillRect(x, canvas.height - barHeight/2, barWidth, barHeight/2);
                x += barWidth + 1;
            }
        }
        draw();
    }

    // Export Project Bundle (Download ZIP)
    const downloadAudioBtn = document.getElementById('download-audio-btn');
    if (downloadAudioBtn) {
        downloadAudioBtn.addEventListener('click', () => {
            const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '';
            const API_BASE_URL = isLocalhost ? 'http://127.0.0.1:8080' : 'https://neurocomposer-api.onrender.com';
            window.location.href = `${API_BASE_URL}/download_zip`;
        });
    }

    // Download MIDI Button Logic
    const downloadBtn = document.getElementById('download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '';
            const API_BASE_URL = isLocalhost ? 'http://127.0.0.1:8080' : 'https://neurocomposer-api.onrender.com';
            window.location.href = `${API_BASE_URL}/track`;
        });
    }

    // --- QUICK START TUTORIAL ---
    const tourBtn = document.getElementById('start-tour-btn');
    const closeTourBtn = document.getElementById('close-tutorial-btn');
    const tutorialOverlay = document.getElementById('tutorial-overlay');

    if (tourBtn && closeTourBtn && tutorialOverlay) {
        tourBtn.addEventListener('click', () => {
            tutorialOverlay.style.display = 'flex';
        });
        
        closeTourBtn.addEventListener('click', () => {
            tutorialOverlay.style.display = 'none';
        });
        
        // Show on first load
        if (!localStorage.getItem('tutorial_seen')) {
            setTimeout(() => {
                tutorialOverlay.style.display = 'flex';
                localStorage.setItem('tutorial_seen', 'true');
            }, 1000);
        }
    }

    // --- AI AUTOMATED MASTERING ---
    const masterBtn = document.getElementById('master-btn');
    const masterOverlay = document.getElementById('mastering-overlay');
    const masterProgBar = document.getElementById('mastering-progress-bar');
    const masterTimeTxt = document.getElementById('mastering-time');
    const masterStatusTxt = document.getElementById('mastering-status-text');
    const masterDownloadBtn = document.getElementById('mastering-download-btn');
    const masterCloseBtn = document.getElementById('mastering-close-btn');

    if (masterBtn && masterOverlay) {
        masterBtn.addEventListener('click', async () => {
            if (!audioCtx || maxDuration === 0) {
                alert("You need to generate a track first!");
                return;
            }

            masterOverlay.classList.remove('hidden');
            masterProgBar.style.width = '0%';
            masterProgBar.parentElement.classList.remove('hidden');
            masterDownloadBtn.classList.add('hidden');
            masterCloseBtn.classList.add('hidden');
            masterStatusTxt.textContent = "[ RECORDING WEB AUDIO STREAM ]";
            masterStatusTxt.style.color = "#c084fc";

            stopAll(true);

            const dest = audioCtx.createMediaStreamDestination();
            masterCompressor.connect(dest);
            masterDelayWet.connect(dest);
            
            const recorder = new MediaRecorder(dest.stream);
            let chunks = [];
            recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
            
            recorder.onstop = async () => {
                masterStatusTxt.textContent = "[ APPLYING AI LIMITER & EQ GLUE... ]";
                masterStatusTxt.style.color = "var(--gold-400)";
                masterProgBar.parentElement.classList.add('hidden');
                
                const blob = new Blob(chunks, { type: 'audio/webm' });
                const formData = new FormData();
                formData.append('file', blob, 'master_mix.webm');
                
                try {
                    const res = await fetch('http://127.0.0.1:8080/master_track', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!res.ok) throw new Error("Backend mastering failed");
                    
                    const audioBlob = await res.blob();
                    const url = URL.createObjectURL(audioBlob);
                    
                    // Decode into masterBuffer and redraw
                    const arrayBuffer = await audioBlob.arrayBuffer();
                    masterBuffer = await audioCtx.decodeAudioData(arrayBuffer);
                    if (lastGeneratedData) {
                        drawPianoRoll(lastGeneratedData);
                    }
                    
                    masterStatusTxt.textContent = "[ MASTERING COMPLETE! ]";
                    masterStatusTxt.style.color = "#4ade80"; 
                    
                    masterDownloadBtn.href = url;
                    masterDownloadBtn.download = "Mastered_NeuroComposer_Track.wav";
                    masterDownloadBtn.classList.remove('hidden');
                    masterCloseBtn.classList.remove('hidden');
                    
                } catch(err) {
                    console.error("Mastering Error:", err);
                    masterStatusTxt.textContent = "[ ERROR: FAILED TO MASTER ]";
                    masterStatusTxt.style.color = "#f87171";
                    masterCloseBtn.classList.remove('hidden');
                }
                
                masterCompressor.disconnect(dest);
                masterDelayWet.disconnect(dest);
            };

            recorder.start();
            isLooping = false; 
            playAll();
            
            const recInterval = setInterval(() => {
                if (!isPlaying) {
                    clearInterval(recInterval);
                    recorder.stop();
                    return;
                }
                let elapsed = audioCtx.currentTime - startTime;
                if (elapsed >= maxDuration) elapsed = maxDuration;
                
                masterProgBar.style.width = `${(elapsed / maxDuration) * 100}%`;
                masterTimeTxt.textContent = `${formatTime(elapsed)} / ${formatTime(maxDuration)}`;
                
                if (elapsed >= maxDuration) {
                    clearInterval(recInterval);
                    stopAll(true);
                    recorder.stop();
                }
            }, 50);
        });
        
        masterCloseBtn.addEventListener('click', () => {
            masterOverlay.classList.add('hidden');
        });
    }

    // --- HOVER TOOLTIPS (Expanded for whole project) ---
    const tooltips = {
        'start-tour-btn': 'Take a quick guided tour of the studio',
        'download-btn': 'Download the raw MIDI files for this track',
        'download-audio-btn': 'Download the raw Audio Stems as a .zip file',
        'generate-btn': 'Click to generate a brand new track using the AI engine',
        'instrument-select': 'Choose the primary Lead Instrument sound',
        'creativity-slider': 'Adjust how wild and unpredictable the AI generation is',
        'chord-progression': 'Force the AI to use a specific chord progression',
        'drum-groove': 'Force a specific drum pattern style',
        'tempo-slider': 'Adjust the speed of the track (BPM)',
        'duration': 'Set the length of the generated track',
        'record-mic-btn': 'Record a 5-second melody using your microphone',
        'seed-dropzone': 'Drag and drop an audio file to use as a melody seed',
        'virtual-piano': 'Click the keys to draw a starting melody',
        'clear-seed': 'Clear the current melody seed',
        'loop-toggle-btn': 'Toggle loop mode on/off',
        'loop-in-btn': 'Set loop start point',
        'loop-out-btn': 'Set loop end point',
        'seek-slider': 'Scrub through the track timeline',
        'daw-play-btn': 'Play the live mixer',
        'daw-stop-btn': 'Stop playback',
        'lock-lead': 'Lock Lead stem so it is not overwritten on next generate',
        'lock-chords': 'Lock Chords stem so it is not overwritten on next generate',
        'lock-bass': 'Lock Bass stem so it is not overwritten on next generate',
        'lock-drums': 'Lock Drums stem so it is not overwritten on next generate',
        'mute-lead': 'Toggle Mute for Lead',
        'mute-chords': 'Toggle Mute for Chords',
        'mute-bass': 'Toggle Mute for Bass',
        'mute-drums': 'Toggle Mute for Drums',
        'vol-lead': 'Lead Volume Fader',
        'vol-chords': 'Chords Volume Fader',
        'vol-bass': 'Bass Volume Fader',
        'vol-drums': 'Drums Volume Fader',
        'rev-lead': 'Lead Reverb Amount', 'del-lead': 'Lead Delay Amount', 'dist-lead': 'Lead Distortion Amount', 'lpf-lead': 'Lead Low-Pass Filter',
        'rev-chords': 'Chords Reverb Amount', 'del-chords': 'Chords Delay Amount', 'dist-chords': 'Chords Distortion Amount', 'lpf-chords': 'Chords Low-Pass Filter',
        'rev-bass': 'Bass Reverb Amount', 'del-bass': 'Bass Delay Amount', 'dist-bass': 'Bass Distortion Amount', 'lpf-bass': 'Bass Low-Pass Filter',
        'rev-drums': 'Drums Reverb Amount', 'del-drums': 'Drums Delay Amount', 'dist-drums': 'Drums Distortion Amount', 'lpf-drums': 'Drums Low-Pass Filter',
        'master-comp': 'Master Compressor Threshold',
        'master-eq-low': 'Master EQ Low Shelf (Bass)',
        'master-eq-mid': 'Master EQ Peaking (Mids)',
        'master-eq-high': 'Master EQ High Shelf (Treble)',
        'master-delay': 'Master Global Delay Amount',
        'master-distortion': 'Master Global Distortion',
        'master-btn': 'Apply AI limiting and bounce a final Master Track'
    };
    // Create global tooltip element
    const tooltipEl = document.createElement('div');
    tooltipEl.className = 'custom-tooltip';
    document.body.appendChild(tooltipEl);

    for (const [id, text] of Object.entries(tooltips)) {
        const el = document.getElementById(id);
        if (el) {
            // Remove native title if it exists to prevent double tooltips
            el.removeAttribute('title');
            
            el.addEventListener('mouseenter', (e) => {
                tooltipEl.textContent = text;
                tooltipEl.style.opacity = '1';
                // Position initially
                tooltipEl.style.transform = `translate(${e.clientX + 15}px, ${e.clientY + 15}px)`;
            });
            
            el.addEventListener('mousemove', (e) => {
                tooltipEl.style.transform = `translate(${e.clientX + 15}px, ${e.clientY + 15}px)`;
            });
            
            el.addEventListener('mouseleave', () => {
                tooltipEl.style.opacity = '0';
            });
        }
    }
});
