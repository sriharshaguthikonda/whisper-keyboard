# Audio callback chunk-buffer fix

Related issue: #13

## Problem

The audio callback should not grow the full recording array on every microphone callback. That pattern repeatedly reallocates and copies previous audio while the stream is active.

## Intended runtime change

Use a Python list of audio chunks during recording. Each callback should only store a copy of the incoming block. When recording stops, concatenate chunks once, flatten to one-dimensional float32 audio, then queue the result for transcription.

## Minimal implementation shape

```python
audio_chunks = []

def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_chunks.append(indata.copy())

def build_recorded_audio():
    if not audio_chunks:
        return np.array([], dtype="float32")
    return np.concatenate(audio_chunks, axis=0).reshape(-1).astype("float32", copy=False)
```

Then stop-recording should call `build_recorded_audio()`, clear `audio_chunks`, and put the resulting array into the transcription queue.

## Notes

This change should not alter Groq/local transcription choice. It is only an internal recording-buffer change.

For the newer prebuffer branch, the queued payload should remain:

```text
prebuffer + recorded_audio
```

The only change is how `recorded_audio` is collected before stop.
