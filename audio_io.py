import asyncio
import collections
import queue
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"
FRAME_SAMPLES = 480  # 20ms at 24kHz
OUTPUT_BLOCKSIZE = 2400  # 100ms at 24kHz — smoother playback


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
    """Continuous byte-buffer approach for glitch-free streaming playback."""

    def __init__(self):
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None

    def _callback(self, outdata, frames, time_info, status):
        if status:
            print(f"[AudioOutput] {status}")
        need_bytes = frames * 2  # int16 = 2 bytes per sample
        with self._lock:
            available = len(self._buf)
            if available >= need_bytes:
                data = bytes(self._buf[:need_bytes])
                del self._buf[:need_bytes]
            elif available > 0:
                # Partial — pad remainder with silence
                data = bytes(self._buf) + b"\x00" * (need_bytes - available)
                self._buf.clear()
            else:
                data = b"\x00" * need_bytes
        outdata[:, 0] = np.frombuffer(data, dtype=np.int16)

    def start(self):
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=OUTPUT_BLOCKSIZE,
            callback=self._callback,
        )
        self._stream.start()

    def write(self, pcm_bytes: bytes):
        with self._lock:
            self._buf.extend(pcm_bytes)

    def flush(self):
        with self._lock:
            self._buf.clear()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
