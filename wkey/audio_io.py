import time
import logging

import numpy as np
import sounddevice as sd


def create_audio_buffers(
    *,
    buffer_size: int,
    sample_rate: int,
    channels: int,
    pre_recording_f24_seconds: int = 3,
):
    pre_recording_buffer = np.zeros((buffer_size, channels), dtype=np.float32)
    pre_recording_buffer_f24 = np.zeros(
        (sample_rate * pre_recording_f24_seconds, channels), dtype=np.float32
    )
    buffer_index = 0
    audio_buffer = []
    return pre_recording_buffer, pre_recording_buffer_f24, buffer_index, audio_buffer


def audio_callback(
    *,
    indata,
    frames,
    time_info,
    status,
    is_recording,
    buffer_index,
    audio_buffer,
    pre_recording_buffer,
    pre_recording_buffer_f24,
    buffer_size,
    max_recording_samples=None,
    recording_lock,
    audio_data_lock,
    log=logging,
    warning_color_prefix="",
    warning_color_suffix="",
    error_color_prefix="",
    error_color_suffix="",
):
    _ = time_info
    try:
        if status:
            log.warning(
                f"{warning_color_prefix}Audio callback status: {status}{warning_color_suffix}"
            )
            return buffer_index, audio_buffer

        with recording_lock:
            if is_recording():
                if isinstance(indata, np.ndarray):
                    with audio_data_lock:
                        if not isinstance(audio_buffer, list):
                            audio_buffer = [np.asarray(audio_buffer, dtype=np.float32).flatten()]
                        audio_buffer.append(indata[:frames].flatten().copy())
                        if max_recording_samples:
                            try:
                                cap = int(max_recording_samples)
                            except Exception:
                                cap = 0
                            total = sum(len(chunk) for chunk in audio_buffer)
                            while cap > 0 and audio_buffer and total > cap:
                                first = audio_buffer[0]
                                overflow = total - cap
                                if overflow >= len(first):
                                    total -= len(first)
                                    audio_buffer.pop(0)
                                else:
                                    audio_buffer[0] = first[int(overflow) :]
                                    total = cap
                else:
                    log.error(
                        f"{error_color_prefix}Invalid indata type: {type(indata)}{error_color_suffix}"
                    )
            else:
                def _write_circular(buffer, start_idx, data):
                    buf_len = len(buffer)
                    if buf_len == 0:
                        return
                    data_len = len(data)
                    if data_len >= buf_len:
                        buffer[:] = data[-buf_len:]
                        return
                    start_idx = start_idx % buf_len
                    first_len = min(data_len, buf_len - start_idx)
                    if first_len > 0:
                        buffer[start_idx : start_idx + first_len] = data[:first_len]
                    remaining = data_len - first_len
                    if remaining > 0:
                        buffer[0:remaining] = data[first_len:first_len + remaining]

                chunk = indata[:frames]
                _write_circular(pre_recording_buffer, buffer_index, chunk)
                if pre_recording_buffer_f24 is not None:
                    f24_len = len(pre_recording_buffer_f24)
                    if f24_len:
                        _write_circular(
                            pre_recording_buffer_f24,
                            buffer_index % f24_len,
                            chunk,
                        )
                buffer_index = (buffer_index + len(chunk)) % buffer_size
    except Exception as e:
        log.error(
            f"{error_color_prefix}Error in audio_callback: {e}{error_color_suffix}",
            exc_info=True,
        )

    return buffer_index, audio_buffer


def get_default_input_device(log=logging):
    try:
        query_devices = getattr(sd, "query_devices", None)
        if query_devices is not None:
            query_devices(None, "input")
    except Exception as e:
        log.debug("Could not query default input device details: %s", e)

    try:
        default_device = getattr(getattr(sd, "default", None), "device", None)
        if isinstance(default_device, (list, tuple)):
            input_device = default_device[0] if default_device else None
        else:
            input_device = default_device
        if input_device in (None, -1):
            return None
        return input_device
    except Exception as e:
        log.debug("Could not resolve default input device: %s", e)
        return None


def initialize_input_stream(
    *,
    stream,
    audio_callback,
    sample_rate: int,
    log=logging,
    success_color_prefix="",
    success_color_suffix="",
    error_color_prefix="",
    error_color_suffix="",
):
    try:
        if stream:
            if not stream.active:
                stream.start()
            return True, stream
    except Exception:
        try:
            stream.close()
        except Exception:
            pass
        stream = None

    try:
        input_device = get_default_input_device(log=log)
        stream = sd.InputStream(
            callback=audio_callback,
            device=input_device,
            channels=1,
            samplerate=sample_rate,
            blocksize=int(sample_rate * 0.1),
        )
        stream.start()
        log.info(
            f"{success_color_prefix}Microphone input stream initialized{success_color_suffix}"
        )
        return True, stream
    except Exception as e:
        log.info(
            f"{error_color_prefix}No microphone detected for input stream: {e}{error_color_suffix}"
        )
        return False, None


def snapshot_audio_buffer(audio_buffer, audio_data_lock):
    with audio_data_lock:
        if isinstance(audio_buffer, list):
            if not audio_buffer:
                return np.array([], dtype=np.float32)
            if all(isinstance(chunk, np.ndarray) for chunk in audio_buffer):
                return np.concatenate(audio_buffer).astype(np.float32, copy=False)
            return np.array(audio_buffer, dtype=np.float32)
        return audio_buffer.copy()


def wait_for_silence(
    *,
    stream,
    audio_buffer,
    audio_data_lock,
    vad_detector,
    sample_rate: int,
    hard_stop_limit: float,
    stop_delay_threshold: float,
    log=logging,
    voice_detected_prefix="",
    voice_detected_suffix="",
    vad_error_prefix="",
    vad_error_suffix="",
    hard_stop_prefix="",
    hard_stop_suffix="",
    stream_inactive_prefix="",
    stream_inactive_suffix="",
):
    silent_time = 0
    recording_start_time = time.time()
    while silent_time <= stop_delay_threshold:
        if stream and getattr(stream, "active", False):
            local_audio_buffer = snapshot_audio_buffer(
                audio_buffer, audio_data_lock
            )
            frame_duration = 30
            frame_size = int(sample_rate * frame_duration / 1000)
            audio_frame = local_audio_buffer[-frame_size:]
            audio_int16 = (audio_frame * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            try:
                is_speech = vad_detector.vad.is_speech(
                    audio_bytes, vad_detector.sample_rate
                )
                if is_speech:
                    silent_time = 0
                    log.info(
                        f"{voice_detected_prefix}Voice detected, continuing recording...{voice_detected_suffix}"
                    )
                else:
                    silent_time += 0.1
            except Exception as e:
                log.error(
                    f"{vad_error_prefix}VAD error: {e}{vad_error_suffix}",
                    exc_info=True,
                )
                silent_time += 0.1

            if time.time() - recording_start_time > hard_stop_limit:
                log.info(
                    f"{hard_stop_prefix}Hard stop limit reached, stopping recording.{hard_stop_suffix}"
                )
                break

            time.sleep(0.1)
        else:
            log.info(
                f"{stream_inactive_prefix}Input stream inactive. Stopping recording.{stream_inactive_suffix}"
            )
            break
