"""Optional offline whisper.cpp adapter. The owner supplies local executable/model.

No auto-download, shell, remote URL, microphone access or provider fallback.
Only bounded 16-bit mono PCM WAV data is accepted.
"""
import io
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import wave

MAX_WAV = 2 * 1024 * 1024
MAX_SECONDS = 60
_slot = threading.Lock()


def configured():
    binary = Path(os.environ.get("KINGDOM_WHISPER_CLI", ""))
    model = Path(os.environ.get("KINGDOM_WHISPER_MODEL", ""))
    if not (binary.is_absolute() and model.is_absolute() and binary.is_file() and model.is_file()):
        return None
    if model.stat().st_size > 250 * 1024 * 1024:
        return None
    return binary, model


def validate_wav(data):
    if not isinstance(data, bytes) or not 44 <= len(data) <= MAX_WAV:
        raise ValueError("Choose a WAV up to 2 MiB")
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            if (audio.getnchannels()!=1 or audio.getsampwidth()!=2 or rate!=16000
                    or audio.getcomptype()!="NONE" or not 0 < frames <= MAX_SECONDS*rate
                    or len(audio.readframes(frames))!=frames*2):
                raise ValueError("Use mono 16 kHz 16-bit PCM WAV up to 60 seconds")
    except (wave.Error, EOFError) as error:
        raise ValueError("Invalid WAV input") from error


def transcribe(data):
    validate_wav(data)
    paths = configured()
    if paths is None:
        raise RuntimeError("Configure local whisper.cpp CLI and a small local model")
    if not _slot.acquire(blocking=False):
        raise RuntimeError("Local transcription slot busy")
    try:
        binary, model = paths
        with tempfile.TemporaryDirectory(prefix="kingdom-voice-") as directory:
            root = Path(directory)
            source = root / "input.wav"
            source.write_bytes(data)
            output = root / "transcript"
            argv = [str(binary), "-m", str(model), "-f", str(source), "-otxt", "-of", str(output), "-t", "2", "-nt", "-np"]
            # Only ordinary OS loader variables; no API credentials.
            env = {key: os.environ[key] for key in ("PATH","SystemRoot","WINDIR","TEMP","TMP","LANG","LD_LIBRARY_PATH","DYLD_LIBRARY_PATH") if key in os.environ}
            subprocess.run(argv, cwd=root, env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=120, check=True, shell=False)
            result = output.with_suffix(".txt")
            if not result.is_file() or result.is_symlink() or result.stat().st_size > 96000:
                raise RuntimeError("Local transcript unavailable or oversized")
            text = result.read_text(encoding="utf-8").strip()
            if not text or len(text)>24000:
                raise RuntimeError("No usable local transcript")
            return {"text":text,"provider":"configured_local_whisper_cpp","requires_review":True}
    finally:
        _slot.release()
