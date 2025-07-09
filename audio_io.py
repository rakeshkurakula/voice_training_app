"""Real‑time audio I/O and local STT/TTS workers."""
from __future__ import annotations
import asyncio, queue, threading, subprocess, wave, pathlib, time
from typing import AsyncGenerator
from logging_utils import log_call
import logging
import tempfile
import os

FRAME_MS = 33  # 30 FPS default

class MicStreamer:
    """Pushes raw 16‑kHz PCM frames to a queue."""

    def __init__(self, frame_ms: int = FRAME_MS):
        logging.info("[MicStreamer] Initializing microphone stream with frame_ms=%s", frame_ms)
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

class WhisperWorker:
    """Handles transcription by writing PCM to temp WAV and calling whisper-cli."""
    def __init__(self, model_path):
        self.model = model_path
        self.language = "en"

    def pcm_to_wav(self, pcm_bytes, wav_path, sample_rate=16000):
        with wave.open(wav_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)

    def transcribe(self, pcm_bytes):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            self.pcm_to_wav(pcm_bytes, tmp_wav.name)
            tmp_filename = tmp_wav.name
        try:
            result = subprocess.run([
                "./whisper.cpp/build/bin/whisper-cli",
                "-m", self.model,
                "-f", tmp_filename,
                "--language", self.language,
                "--output-format", "txt"
            ], capture_output=True, text=True)
            if result.returncode != 0:
                print("Whisper CLI error:", result.stderr)
                return None
            return result.stdout.strip()
        finally:
            os.unlink(tmp_filename)

async def transcribe_stream(model_path: str) -> AsyncGenerator[str, None]:
    logging.info("[transcribe_stream] Starting transcription stream with model=%s", model_path)
    worker = WhisperWorker(model_path)
    async for chunk in pcm_generator():
        transcript = worker.transcribe(chunk)
        if transcript:
            yield transcript

class PiperWorker(threading.Thread):
    """Wraps Piper TTS for local text-to-speech."""
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

async def play_tts(text: str, voice_path: str = "models/piper/en_US-amy-medium.onnx") -> str:
    """Synthesize and play text using Piper TTS. Returns path to generated audio."""
    worker = PiperWorker(voice_path)
    output_path = f"/tmp/tts_{int(time.time())}.wav"
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, worker.synthesize, text, output_path)
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
    print(f"🎤 Reference: {reference_text}")
    await play_tts(reference_text, voice_path)
    print("🎤 Your turn - repeat the text...")

async def feedback_mode(user_audio_path: str, reference_text: str, voice_path: str = "models/piper/en_US-amy-medium.onnx"):
    print("🎤 Playing your pronunciation...")
    await play_audio_file(user_audio_path)
    print("🎤 Playing reference pronunciation...")
    await play_tts(reference_text, voice_path)
