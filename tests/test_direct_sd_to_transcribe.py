import numpy as np

from wkey import direct_sd_to_transcribe as direct_sd


def test_audio_callback_buffers_copied_chunks_until_recording_finishes():
    direct_sd.audio_buffer = np.empty((0, 1), dtype="float32")
    direct_sd.audio_chunks = []

    first = np.array([[1.0], [2.0], [99.0]], dtype="float32")
    second = np.array([[3.0]], dtype="float32")

    direct_sd.audio_callback(first, 2, None, None)
    first[0, 0] = 42.0
    direct_sd.audio_callback(second, 1, None, None)

    np.testing.assert_array_equal(direct_sd.audio_buffer, np.empty((0, 1), dtype="float32"))
    np.testing.assert_array_equal(
        direct_sd.build_recorded_audio(),
        np.array([[1.0], [2.0], [3.0]], dtype="float32"),
    )
