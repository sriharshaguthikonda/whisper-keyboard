import time
import numpy as np
from openwakeword.model import Model

try:
    import psutil
except ImportError:
    psutil = None


DEFAULT_MODEL_PATHS = [
    r"C:\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_jarvis_v0.1.onnx",
    r"C:\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_computer10.onnx",
    r"C:\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_lama.onnx",
    r"C:\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_google.onnx",
]

DEFAULT_THRESHOLDS = {
    0: 0.9,
    1: 0.05,
    2: 0.1,
    3: 0.01,
}

DEFAULT_CHUNK = 5120
DEFAULT_COOLDOWN = 6
DEFAULT_RELAX_SLEEP = 0.25
DEFAULT_CPU_THRESHOLD = 80.0
DEFAULT_CPU_CHECK_INTERVAL = 1.0


class WakeWordListener:
    def __init__(
        self,
        model_paths=None,
        thresholds=None,
        chunk=DEFAULT_CHUNK,
        cooldown=DEFAULT_COOLDOWN,
        vad_threshold=0.3,
        relax_sleep=DEFAULT_RELAX_SLEEP,
        cpu_threshold=DEFAULT_CPU_THRESHOLD,
        cpu_check_interval=DEFAULT_CPU_CHECK_INTERVAL,
    ):
        if model_paths is None:
            model_paths = DEFAULT_MODEL_PATHS
        if thresholds is None:
            thresholds = DEFAULT_THRESHOLDS

        self.model = Model(
            wakeword_models=model_paths,
            inference_framework="onnx",
            vad_threshold=vad_threshold,
        )
        self.thresholds = thresholds
        self.chunk = chunk
        self.cooldown = cooldown
        self.last_detection_time = 0
        self.relax_sleep = relax_sleep
        self.cpu_threshold = cpu_threshold
        self.cpu_check_interval = cpu_check_interval
        self._last_cpu_check = 0.0
        self._last_cpu_percent = 0.0

    def _cpu_overloaded(self):
        if psutil is None or self.cpu_threshold is None:
            return False
        now = time.time()
        if now - self._last_cpu_check >= self.cpu_check_interval:
            self._last_cpu_percent = psutil.cpu_percent(interval=None)
            self._last_cpu_check = now
        return self._last_cpu_percent >= self.cpu_threshold

    def listen(
        self,
        get_wake_stream,
        set_wake_stream,
        check_pause_status,
        is_recording,
        start_recording_async,
        stop_recording_async,
        decrease_volume_all,
        restore_volume_all,
        heartbeat=None,
        should_relax=None,
        log=print,
    ):
        log("Listening for wake words...")

        while True:
            try:
                if heartbeat:
                    heartbeat()
                if check_pause_status():
                    time.sleep(1)
                    continue

                wake_stream = get_wake_stream()
                if wake_stream:
                    data = wake_stream.read(self.chunk, exception_on_overflow=False)

                    if (should_relax and should_relax()) or self._cpu_overloaded():
                        time.sleep(self.relax_sleep)
                        continue

                    pcm = np.frombuffer(data, dtype=np.int16)

                    _ = self.model.predict(pcm)
                    keyword_index = -1
                    max_score = 0.0

                    recent_predictions = list(self.model.prediction_buffer.values())[-8:]

                    for idx, scores in enumerate(recent_predictions):
                        if scores[-1] > max_score:
                            max_score = scores[-1]
                            keyword_index = idx

                    current_time = time.time()
                    if (
                        keyword_index >= 0
                        and max_score > self.thresholds.get(keyword_index, 0.4)
                        and (current_time - self.last_detection_time) > self.cooldown
                        and not is_recording()
                        and not check_pause_status()
                    ):
                        self.last_detection_time = current_time

                        if keyword_index == 0:
                            log("Custom wake word 'hey_jarvis' detected!")
                            start_recording_async(keyword_index)
                            time.sleep(3)
                            stop_recording_async(keyword_index)
                        elif keyword_index == 1:
                            log("Custom wake word 'hey_computer10' detected!")
                            start_recording_async(keyword_index)
                            stop_recording_async(1)
                        elif keyword_index == 2:
                            log("Custom wake word 'hey_lama' detected!")
                            start_recording_async(keyword_index)
                            stop_recording_async(2)
                        elif keyword_index == 3:
                            log("Custom wake word 'hey_google' detected!")
                            decrease_volume_all()
                            time.sleep(3)
                            restore_volume_all()
                else:
                    log("Waiting for microphone...")
                    time.sleep(5)

            except OSError as e:
                log(f"Audio stream error: {e}")
                wake_stream = get_wake_stream()
                if wake_stream:
                    try:
                        if wake_stream.is_active():
                            wake_stream.stop_stream()
                        wake_stream.close()
                    except OSError:
                        log("Stream already closed or failed to close.")
                set_wake_stream(None)
                time.sleep(10)
