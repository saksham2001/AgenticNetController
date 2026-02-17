import asyncio
import queue

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"
FRAME_SAMPLES = 480  # 20ms at 24kHz


class AudioInput:
    def __init__(self):
        self._queue: asyncio.Queue[bytes] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[AudioInput] {status}")
        pcm = indata.copy().tobytes()
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, pcm)

    def start(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._queue = asyncio.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=FRAME_SAMPLES,
            callback=self._callback,
        )
        self._stream.start()

    async def read_frame(self) -> bytes:
        return await self._queue.get()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class AudioOutput:
    def __init__(self):
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.OutputStream | None = None

    def _callback(self, outdata, frames, time_info, status):
        if status:
            print(f"[AudioOutput] {status}")
        written = 0
        buf = np.zeros((frames, CHANNELS), dtype=DTYPE)
        while written < frames:
            try:
                chunk = self._queue.get_nowait()
            except queue.Empty:
                break
            remaining = frames - written
            use = min(len(chunk), remaining)
            buf[written : written + use, 0] = chunk[:use]
            written += use
            if use < len(chunk):
                # Push back leftover
                self._queue.put(chunk[use:])
                break
        outdata[:] = buf

    def start(self):
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=FRAME_SAMPLES,
            callback=self._callback,
        )
        self._stream.start()

    def write(self, pcm_bytes: bytes):
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        self._queue.put(samples)

    def flush(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
