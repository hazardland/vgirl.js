from TTS.api import TTS
import sounddevice as sd
import numpy as np

# Load the XTTS v2 model
print("Loading XTTS v2 model...")
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
print("Model loaded successfully!")

# Text to synthesize
text = "Hello! This is an example of XTTS v2 multilingual TTS."

# Path to the voice sample for cloning
speaker_wav_path = "./female.wav"  # Replace with the path to your audio sample

# Generate speech with the specified speaker
print("Generating speech with cloned voice...")
waveform = tts.tts(text=text, speaker_wav=speaker_wav_path, language="en")

# Play the generated audio
print("Playing audio...")
sd.play(np.array(waveform), samplerate=tts.synthesizer.output_sample_rate)
sd.wait()  # Wait for playback to complete
print("Playback complete!")
