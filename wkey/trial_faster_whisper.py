import pyaudio
import numpy as np
import wave
import keyboard
import noisereduce as nr
import soundfile as sf
import librosa
import queue

from faster_whisper import WhisperModel

# Preload noise sample
noise_sample_path = r'C:\Users\deletable\OneDrive\Windows_software\openai whisper\baseline_recording_for_noise_reduction.wav'
noise_sample, sr_noise_sample = librosa.load(noise_sample_path, sr=16000)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Audio stream parameters
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 16000
CHUNK = 32000

# Initialize a buffer to store recorded audio
audio_buffer = queue.Queue()

def callback(in_data, frame_count, time_info, status):
    if is_recording:
        audio_buffer.put(in_data)
    return (None, pyaudio.paContinue)

# Open stream
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                output=False,  # Set to False as we're not playing back
                frames_per_buffer=CHUNK,
                stream_callback=callback)

is_recording = False

def toggle_recording(e):
    global is_recording
    is_recording = not is_recording
    if not is_recording:
        # Stop recording; process and save the audio
        process_and_save_audio()
    print(f"Recording {'started' if is_recording else 'stopped'}.")

keyboard.on_press_key("space", toggle_recording)




#model = whisper.load_model("tiny.en")
#model = WhisperModel("tiny.en")
model = WhisperModel("small.en")


def process_and_save_audio():
    # Fetch all audio chunks from the buffer and process them individually
    transcripts = []  # To store all transcripts
    processed_chunks = []
    unprocessed_chunks = []
    while not audio_buffer.empty():
        data = audio_buffer.get()
        audio_chunk = np.frombuffer(data, dtype=np.float32)
        
        # Apply noise reduction to each chunk
        reduced_chunk = nr.reduce_noise(
            y=audio_chunk,
            sr=RATE,
            y_noise=noise_sample,
            stationary=False,
            prop_decrease=1.0,
            n_std_thresh_stationary=2.0,
            freq_mask_smooth_hz=200,  # Aggressive frequency smoothing
            time_mask_smooth_ms=32,  # Minimum requirement for smoothing over time
            thresh_n_mult_nonstationary=1.5,
            sigmoid_slope_nonstationary=8,
            n_fft=2048,
            win_length=None,
            hop_length=512,
            use_torch=True,
            use_tqdm=True
        )

        processed_chunks.append(reduced_chunk)
        unprocessed_chunks.append(audio_chunk)
    
    if processed_chunks:
        # Concatenate all processed chunks
        processed_audio = np.concatenate(processed_chunks)
        unprocessed_audio = np.concatenate(unprocessed_chunks)
        
        # Transcribe processed audio
        segments, info = model.transcribe(processed_audio)
        transcript_processed = " ".join([segment.text for segment in segments])
        print("Processed Audio Transcript:", transcript_processed)
        
        # Transcribe unprocessed audio
        segments, info = model.transcribe(unprocessed_audio)
        transcript_unprocessed = " ".join([segment.text for segment in segments])
        print("Unprocessed Audio Transcript:", transcript_unprocessed)
        
        # Save the processed audio
        sf.write('processed_recording.wav', processed_audio, RATE)
        sf.write('unprocessed_recording.wav', unprocessed_audio, RATE)
        print("Audio processed and saved.")


  

"""
 # Transcribe processed audio
segments, info = model.transcribe("processed_recording.wav")
transcript_processed = " ".join([segment.text for segment in segments])
print("Processed Audio Transcript:", transcript_processed)

# Transcribe unprocessed audio
segments, info = model.transcribe("unprocessed_recording.wav")
transcript_unprocessed = " ".join([segment.text for segment in segments])
print("Unprocessed Audio Transcript:", transcript_unprocessed)

"""

# Start the stream
stream.start_stream()

print("Press space to start/stop recording. Press 'esc' to exit.")
keyboard.wait('esc')


# Cleanup
stream.stop_stream()
stream.close()
p.terminate()
