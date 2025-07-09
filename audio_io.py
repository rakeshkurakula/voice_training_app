"""Real‑time audio I/O and local STT/TTS workers."""
from __future__ import annotations
import asyncio, queue, threading, subprocess, wave, pathlib, time
from typing import AsyncGenerator
from logging_utils import log_call

FRAME_MS = 33  # 30 FPS default

class MicStreamer:
    """Pushes raw 16‑kHz PCM frames to a queue."""

    def __init__(self, frame_ms: int = FRAME_MS):
        import pyaudio                       # lazy‑import
        self.p = pyaudio.PyAudio()
        self.frame_samples = int(16_000 * frame_ms / 1000)
        self.q: queue.Queue[bytes] = queue.Queue(maxsize=100)

        self.stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                  rate=16_000, input=True,
                                  frames_per_buffer=self.frame_samples,
                                  stream_callback=self._callback)

    def _callback(self, in_data, frame_count, *_):
        try: self.q.put_nowait(in_data)
        except queue.Full: pass
        return (None, 0)

    def start(self): self.stream.start_stream()
    def stop(self):  self.stream.stop_stream(); self.stream.close(); self.p.terminate()

async def pcm_generator(ms: int = FRAME_MS) -> AsyncGenerator[bytes, None]:
    mic = MicStreamer(ms); mic.start()
    loop = asyncio.get_event_loop()
    while True:
        data = await loop.run_in_executor(None, mic.q.get)
        yield data

class WhisperWorker(threading.Thread):
    """Wraps whisper.cpp cli for streaming transcription."""

    @log_call
    def __init__(self, model: str):
        super().__init__(daemon=True)
        self.proc = subprocess.Popen(
            ["./whisper.cpp/build/bin/main", "-m", model, "-f", "-"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True, bufsize=0)
        self.lines = queue.Queue()

    @log_call
    def run(self):
        for line in self.proc.stdout:
            self.lines.put(line.strip())

    @log_call
    def push_audio(self, pcm: bytes): self.proc.stdin.write(pcm)

    @log_call
    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None

class PiperWorker(threading.Thread):
    """Wraps Piper TTS for local text-to-speech."""

    @log_call
    def __init__(self, voice_path: str):
        super().__init__(daemon=True)
        self.voice_path = voice_path
        self.proc = None

    @log_call
    def synthesize(self, text: str, output_path: str):
        """Synthesize text to audio file."""
        if self.proc:
            self.proc.terminate()
        self.proc = subprocess.Popen([
            "piper", "--model", self.voice_path,
            "--output_file", output_path
        ], stdin=subprocess.PIPE, text=True)
        self.proc.communicate(input=text)

    @log_call
    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None

async def transcribe_stream(model: str) -> AsyncGenerator[str, None]:
    worker = WhisperWorker(model); worker.start()
    async for chunk in pcm_generator():
        worker.push_audio(chunk)
        try:
            while True: yield worker.lines.get_nowait()
        except queue.Empty:
            continue

async def play_tts(text: str, voice_path: str = "models/piper/en_US-amy-medium.onnx") -> str:
    """Synthesize and play text using Piper TTS. Returns path to generated audio."""
    worker = PiperWorker(voice_path)
    output_path = f"/tmp/tts_{int(time.time())}.wav"
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, worker.synthesize, text, output_path)
    
    # Play the audio (platform-specific)
    await play_audio_file(output_path)
    return output_path

async def play_audio_file(file_path: str):
    """Play audio file using system audio player."""
    import platform
    system = platform.system()
    
    if system == "Darwin":  # macOS
        subprocess.run(["afplay", file_path])
    elif system == "Linux":
        subprocess.run(["aplay", file_path])
    else:  # Windows
        subprocess.run(["start", file_path], shell=True)

async def practice_mode(reference_text: str, voice_path: str = "models/piper/en_US-amy-medium.onnx"):
    """Practice mode: TTS speaks reference, user repeats."""
    print(f"🎤 Reference: {reference_text}")
    await play_tts(reference_text, voice_path)
    print("🎤 Your turn - repeat the text...")
    # Continue with user's speech input...

async def feedback_mode(user_audio_path: str, reference_text: str, voice_path: str = "models/piper/en_US-amy-medium.onnx"):
    """Feedback mode: Compare user's pronunciation with TTS reference."""
    print("🎤 Playing your pronunciation...")
    await play_audio_file(user_audio_path)
    
    print("🎤 Playing reference pronunciation...")
    await play_tts(reference_text, voice_path)
