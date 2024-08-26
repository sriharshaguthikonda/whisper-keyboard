Sure! Below is a detailed `README.md` for your project.

---

# Whisper Keyboard with Wake Word Detection

This project is a voice recognition system that enables dictation and transcription using wake word detection. The system listens for a specific wake word ("Hey llama") and then records and transcribes your speech. It includes functionalities such as audio volume management, clipboard handling, and seamless transcription using both local models and the Groq API.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Microphone Handling](#microphone-handling)
- [Components Overview](#components-overview)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- **Wake Word Detection:** Uses Porcupine's custom wake word model to start recording when a specific phrase is detected.
- **Flexible Transcription:** Automatically transcribes speech using the Groq API or a local Whisper model, depending on availability.
- **Clipboard Management:** Automatically pastes the transcribed text into the active window.
- **Volume Control:** Automatically adjusts the system volume during recording to minimize background noise interference.
- **Error Handling:** Pauses wake word detection if no microphone is detected and resumes once reconnected.

## Installation

### Prerequisites

- Python 3.8 or higher
- A CUDA-compatible GPU for Whisper (optional but recommended)
- [Porcupine Access Key](https://picovoice.ai/)
- [Groq API Key](https://groq.com/)

### Dependencies

Install the necessary Python packages using `pip`:

```bash
pip install numpy sounddevice pythoncom scipy pyautogui winsound clipboard pynput python-dotenv faster-whisper vosk pyaudio pvporcupine pycaw groq
```

You may also need to install additional system dependencies like PortAudio for `pyaudio`.

### Model Downloads

- **Vosk Model:** Download a small Vosk model from [here](https://alphacephei.com/vosk/models) and extract it to your desired location. Update the path in the code accordingly.
- **Porcupine Custom Wake Word Model:** Create or download a custom wake word model from [Picovoice Console](https://console.picovoice.ai/) and update the path in the code.

## Usage

1. **Environment Variables:**
   - Create a `.env` file in the project directory.
   - Add the following variables:
     ```plaintext
     GROQ_API_KEY=your_groq_api_key_here
     PICO_ACCESS_KEY=your_picovoice_access_key_here
     WKEY=f24  # Customize the key used for manual recording if needed
     ```

2. **Run the Script:**
   ```bash
   python faster_whisper_Mother_of_all_wkey.py"
   ```
   The system will start listening for the wake word and allow dictation by holding down the specified key (`F24` by default).

## Configuration

### Environment Variables

- **GROQ_API_KEY:** Your API key for accessing Groq's transcription service.
- **PICO_ACCESS_KEY:** Your access key for using Porcupine's wake word detection.
- **WKEY:** The key used to manually start and stop recording.

### Audio Settings

- **Sample Rate:** The system uses an 8000 Hz sample rate by default, but you can adjust it in the script if needed.
- **Volume Levels:** The system decreases the volume to 10% during recording to reduce background noise interference. Adjust the values in `decrease_volume_all` and `restore_volume_all` functions if needed.

## Microphone Handling

If the system detects that no microphone is connected:

- Wake word detection will be paused.
- The system will periodically check for a microphone and resume wake word detection once a microphone is available.
- If you disconnect your microphone while the system is running, it will automatically pause and resume as necessary.

### Checking Microphone Connection

The script uses the `sounddevice` library to check for available input devices. If no microphone is detected, the script waits and checks again every 5 seconds.

## Components Overview

### Core Functions

- **`start_recording`:** Starts recording audio when the wake word is detected or the specified key is pressed.
- **`stop_recording`:** Stops recording and queues the audio buffer for transcription.
- **`transcribe_with_groq`:** Transcribes audio using the Groq API.
- **`transcribe_with_local_model`:** Transcribes audio using a local Whisper model.
- **`clean_transcript`:** Cleans up the transcribed text and pastes it into the active window.
- **`is_microphone_connected`:** Checks if a microphone is connected and functional.

### Threads

- **Wake Word Detection:** Continuously listens for the wake word.
- **Sound Monitoring:** Checks if any audio is playing on the system.
- **Transcription Processing:** Handles audio transcription asynchronously.
- **Clipboard Management:** Manages clipboard content for pasting the transcription.

## Troubleshooting

- **Microphone Not Detected:** Ensure your microphone is properly connected before starting the script. If disconnected during operation, the script will automatically handle reconnection.
- **API Rate Limits:** If you hit the Groq API rate limit, the system will automatically fall back to using the local Whisper model for transcription.
- **Volume Too Low During Playback:** The system reduces volume during recording; make sure it is restored after transcription if you notice low volume.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

---

This `README.md` provides comprehensive information about the project, from installation and usage to troubleshooting and license details. Adjust any specifics based on your exact implementation or requirements.
