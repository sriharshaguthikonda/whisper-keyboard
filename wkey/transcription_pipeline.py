import asyncio
import io
import time
import logging
from queue import Empty as QueueEmpty

from scipy.io.wavfile import write as wav_write


DEFAULT_GROQ_FAILURES_BEFORE_CPU = 3


def run_asyncio_in_thread(loop, coro):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)


class TranscriptionPipeline:
    def __init__(
        self,
        *,
        audio_buffer_queue,
        transcript_queue,
        settings_getter,
        sample_rate,
        validate_audio_buffer,
        transcribe_with_groq_async,
        transcribe_with_local_model,
        model_getter,
        gpu_available_getter,
        initialize_local_model_cpu,
        paste_transcript,
        beep,
        global_state,
        log=logging,
        error_color_prefix="",
        error_color_suffix="",
        groq_failures_before_cpu=DEFAULT_GROQ_FAILURES_BEFORE_CPU,
    ):
        self.audio_buffer_queue = audio_buffer_queue
        self.transcript_queue = transcript_queue
        self.settings_getter = settings_getter
        self.sample_rate = sample_rate
        self.validate_audio_buffer = validate_audio_buffer
        self.transcribe_with_groq_async = transcribe_with_groq_async
        self.transcribe_with_local_model = transcribe_with_local_model
        self.model_getter = model_getter
        self.gpu_available_getter = gpu_available_getter
        self.initialize_local_model_cpu = initialize_local_model_cpu
        self.paste_transcript = paste_transcript
        self.beep = beep
        self.global_state = global_state
        self.log = log
        self.error_color_prefix = error_color_prefix
        self.error_color_suffix = error_color_suffix
        self.groq_failure_streak = 0
        self.groq_failures_before_cpu = groq_failures_before_cpu
        self.global_state.setdefault("transcribe_inflight", False)
        self.global_state.setdefault("last_transcribe_activity", time.time())

    async def process_audio_async(self):
        while True:
            try:
                self.global_state["is_processing"] = True

                try:
                    audio_buffer_for_processing, keyword_index = self.audio_buffer_queue.get(
                        timeout=1
                    )
                except QueueEmpty:
                    self.global_state["is_processing"] = False
                    await asyncio.sleep(0.1)
                    continue

                if not self.validate_audio_buffer(audio_buffer_for_processing):
                    self.global_state["consecutive_failures"] += 1
                    continue

                self.log.info("process_audio_async: Creating WAV buffer")
                byte_io = io.BytesIO()
                wav_write(byte_io, self.sample_rate, audio_buffer_for_processing)
                byte_io.seek(0)
                self.log.info(
                    "process_audio_async: WAV buffer created, size=%d bytes",
                    byte_io.getbuffer().nbytes,
                )

                transcript = None
                groq_success = False
                current_settings = self.settings_getter()
                use_groq = current_settings.get("fallback_to_groq", True)
                max_retries = current_settings.get("max_retries", 3)

                if use_groq:
                    try:
                        self.log.info("process_audio_async: Starting Groq transcription")
                        groq_start_time = time.time()
                        self.global_state["transcribe_inflight"] = True
                        self.global_state["last_transcribe_activity"] = time.time()
                        try:
                            transcript = await self.transcribe_with_groq_async(
                                byte_io, keyword_index, max_retries=max_retries
                            )
                        finally:
                            self.global_state["transcribe_inflight"] = False
                            self.global_state["last_transcribe_activity"] = time.time()
                        self.log.info(
                            "process_audio_async: Groq returned transcript=%r", transcript
                        )
                        if transcript is not None:
                            groq_success = True
                            groq_duration = time.time() - groq_start_time
                            self.log.info(
                                "Groq transcription successful in %.2fs", groq_duration
                            )
                    except Exception as e:
                        self.log.warning(
                            "Groq API error, will try local model: %s", str(e)
                        )

                    if groq_success:
                        self.groq_failure_streak = 0
                    else:
                        self.groq_failure_streak += 1

                    if (
                        not groq_success
                        and self.model_getter() is None
                        and (not self.gpu_available_getter())
                        and current_settings.get("use_local_cpu", True)
                        and self.groq_failure_streak >= self.groq_failures_before_cpu
                    ):
                        self.initialize_local_model_cpu()

                    if not groq_success and self.model_getter() is not None:
                        try:
                            local_start_time = time.time()
                            local_transcript = self.transcribe_with_local_model(
                                audio_buffer_for_processing, keyword_index
                            )
                            if (
                                local_transcript
                                and local_transcript != "Transcription failed"
                            ):
                                local_duration = time.time() - local_start_time
                                self.log.info(
                                    "Local transcription successful in %.2fs",
                                    local_duration,
                                )
                                transcript = local_transcript
                        except Exception as e:
                            self.log.error("Local transcription failed: %s", e)
                else:
                    self.groq_failure_streak = 0
                    if (
                        self.model_getter() is None
                        and current_settings.get("use_local_cpu", True)
                    ):
                        self.initialize_local_model_cpu()
                    if self.model_getter() is None:
                        self.log.error(
                            "Local transcription disabled or unavailable and Groq is disabled in settings"
                        )
                        continue
                    try:
                        local_start_time = time.time()
                        local_transcript = self.transcribe_with_local_model(
                            audio_buffer_for_processing, keyword_index
                        )
                        if local_transcript and local_transcript != "Transcription failed":
                            local_duration = time.time() - local_start_time
                            self.log.info(
                                "Local transcription successful in %.2fs", local_duration
                            )
                            transcript = local_transcript
                    except Exception as e:
                        self.log.error("Local transcription failed: %s", e)

                if not transcript:
                    self.log.error("All transcription attempts failed")
                    continue

                transcript_lower = transcript.lower()
                transcript_stripped = transcript.strip()

                if len(transcript_stripped) < 2:
                    self.log.warning(
                        "Skipping too-short transcript: '%s'", transcript_stripped
                    )
                    continue

                if keyword_index == 0:
                    self.log.info(
                        "Routing F24 transcript directly to execute_command_run_with_tool"
                    )
                    self.transcript_queue.put((transcript_stripped, 0))
                    continue
                if keyword_index is None:
                    self.log.info("pasting manual transcription")
                    self.paste_transcript(transcript, self.beep)
                    continue
                if keyword_index == 1 and "computer" in transcript_lower:
                    keyword_position = transcript_lower.index("computer")
                    stripped_transcript = transcript_lower[
                        keyword_position + len("computer") :
                    ]
                    self.log.info(
                        "Processing computer command: %s", stripped_transcript
                    )
                    self.transcript_queue.put(
                        (stripped_transcript.strip(), keyword_index)
                    )
                    continue
                if keyword_index == 2 and "lama" in transcript_lower:
                    keyword_position = transcript_lower.index("lama")
                    stripped_transcript = transcript_lower[
                        keyword_position + len("lama") :
                    ]
                    self.log.info("Processing lama command: %s", stripped_transcript)
                    self.paste_transcript(stripped_transcript, self.beep)
                    continue
                if keyword_index == 3 and "google" in transcript_lower:
                    keyword_position = transcript_lower.index("google")
                    stripped_transcript = transcript_lower[
                        keyword_position + len("google") :
                    ]
                    self.log.info("Processing google command: %s", stripped_transcript)
                    continue

                self.global_state["last_successful_operation"] = time.time()
                self.global_state["consecutive_failures"] = 0

            except Exception as e:
                self.log.error(
                    "%sProcess audio error: %s%s",
                    self.error_color_prefix,
                    e,
                    self.error_color_suffix,
                    exc_info=True,
                )
                self.global_state["consecutive_failures"] += 1
                if self.global_state["consecutive_failures"] > 3:
                    await asyncio.sleep(1)
            finally:
                self.global_state["is_processing"] = False
