import webrtcvad
import numpy as np
from collections import deque


class VoiceDetector:
    def __init__(self, aggressiveness=2):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = 16000
        self.frame_duration = 30  # ms
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)

        # Speech detection smoothing parameters
        self.speech_history = deque(maxlen=8)  # Maintain history of last 8 frames
        self.speech_threshold = (
            0.4  # Consider speech if 40% of recent frames had speech
        )
        self.gap_tolerance = 3  # Number of silent frames to tolerate

    def is_speech(self, audio_chunk):
        """
        Detect if speech is present in an audio chunk with gap tolerance.
        audio_chunk should be float32 numpy array with values between -1 and 1
        """
        try:
            # Convert float32 to int16
            audio_int16 = (audio_chunk * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            # Get raw speech detection
            is_speech_current = self.vad.is_speech(audio_bytes, self.sample_rate)

            # Add current detection to history
            self.speech_history.append(is_speech_current)

            # Count recent speech frames
            recent_speech_ratio = sum(self.speech_history) / len(self.speech_history)

            # Count consecutive silent frames
            silent_frames = 0
            for frame in reversed(self.speech_history):
                if not frame:
                    silent_frames += 1
                else:
                    break

            # Consider it speech if:
            # 1. Current frame is speech OR
            # 2. Recent history has enough speech AND not too many consecutive silent frames
            return is_speech_current or (
                recent_speech_ratio >= self.speech_threshold
                and silent_frames <= self.gap_tolerance
            )

        except Exception as e:
            print(f"VAD error: {e}")
            return False


if __name__ == "__main__":
    # Simple test
    detector = VoiceDetector()
    # Create 30ms of silence
    silence = np.zeros(480, dtype=np.float32)
    print(f"Silence detection: {detector.is_speech(silence)}")
