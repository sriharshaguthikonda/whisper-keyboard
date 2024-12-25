import webrtcvad
import numpy as np
import sounddevice as sd
import time
import queue


class VoiceDetector:
    def __init__(self):
        # Initialize VAD with moderate aggressiveness
        self.vad = webrtcvad.Vad(2)
        self.sample_rate = 16000
        self.frame_duration = 30  # ms
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)
        self.audio_queue = queue.Queue()
        self.is_running = True

    def audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice to handle incoming audio"""
        if status:
            print(f"Status: {status}")
        try:
            # Convert float32 to int16
            audio_chunk = (indata * 32767).astype(np.int16)
            self.audio_queue.put(audio_chunk)
        except Exception as e:
            print(f"Error in callback: {e}")

    def process_audio(self):
        """Process audio chunks from the queue"""
        while self.is_running:
            try:
                audio_chunk = self.audio_queue.get(timeout=1)
                is_speech = self.vad.is_speech(audio_chunk.tobytes(), self.sample_rate)
                if is_speech:
                    print("\033[92m● Voice Active\033[0m")  # Green dot
                else:
                    print("\033[91m● Silent\033[0m")  # Red dot
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {e}")

    def start(self):
        """Start voice detection"""
        try:
            # List available devices
            print("\nAvailable audio devices:")
            print(sd.query_devices())

            # Get default device
            device_info = sd.query_devices(None, "input")
            print(f"\nUsing device: {device_info['name']}")

            # Start the audio stream
            stream = sd.InputStream(
                channels=1,
                dtype=np.float32,
                samplerate=self.sample_rate,
                blocksize=self.frame_size,
                callback=self.audio_callback,
            )

            print("\nStarting voice detection...")
            with stream:
                import threading

                process_thread = threading.Thread(target=self.process_audio)
                process_thread.start()

                while True:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nStopping voice detection...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.is_running = False


def main():
    detector = VoiceDetector()
    detector.start()


if __name__ == "__main__":
    main()
