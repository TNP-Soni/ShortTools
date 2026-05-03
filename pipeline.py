from kokoro_onnx import Kokoro
import soundfile as sf
import urllib.request
import whisper
import sys
import os

# --- EMBED SCRIPT HERE (leave empty to pass via command line arg instead) ---
TEXT = """
"""
# ----------------------------------------------------------------------------

VOICE = "af_bella"
WHISPER_MODEL = "base"

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")
SUBTITLE_DIR = os.path.join(os.path.dirname(__file__), "subtitles")

_BASE = os.path.dirname(__file__)
_MODEL_PATH = os.path.join(_BASE, "kokoro-v1.0.int8.onnx")
_VOICES_PATH = os.path.join(_BASE, "voices-v1.0.bin")
_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

def _download(url, dest):
    tmp = dest + ".tmp"
    print(f"Downloading {os.path.basename(dest)}...")
    urllib.request.urlretrieve(url, tmp, reporthook=lambda n, bs, ts: print(
        f"\r  {min(n*bs, ts)//1024//1024}MB / {ts//1024//1024}MB", end="", flush=True
    ))
    print()
    os.replace(tmp, dest)

_kokoro = None

def get_kokoro():
    global _kokoro
    if _kokoro is None:
        if not os.path.exists(_MODEL_PATH):
            _download(_MODEL_URL, _MODEL_PATH)
        if not os.path.exists(_VOICES_PATH):
            _download(_VOICES_URL, _VOICES_PATH)
        print("Loading Kokoro model...")
        _kokoro = Kokoro(_MODEL_PATH, _VOICES_PATH)
    return _kokoro

def next_n():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(SUBTITLE_DIR, exist_ok=True)
    existing = [f for f in os.listdir(AUDIO_DIR) if f.startswith("audio_") and f.endswith(".wav")]
    nums = [int(f[6:9]) for f in existing if f[6:9].isdigit()]
    return max(nums) + 1 if nums else 1

def format_time(t):
    ms = int((t - int(t)) * 1000)
    s = int(t)
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def _lang_for_voice(voice):
    return "en-gb" if voice.startswith("b") else "en-us"

def _sanitise(text):
    """Clean up punctuation that Kokoro TTS misreads or speaks literally."""
    return (text
        .replace("\u2014", ", ")   # em dash —
        .replace("\u2013", ", ")   # en dash –
        .replace("\u2026", ".")    # ellipsis …
        .replace("\u2018", "'")    # left single quote
        .replace("\u2019", "'")    # right single quote / apostrophe
        .replace("\u201c", '"')    # left double quote
        .replace("\u201d", '"')    # right double quote
    )

def generate_audio(text, voice, path, speed=1.0):
    kokoro = get_kokoro()
    lang = _lang_for_voice(voice)
    samples, sample_rate = kokoro.create(_sanitise(text), voice=voice, speed=speed, lang=lang)
    sf.write(path, samples, sample_rate)

_whisper_model = None

def transcribe(path):
    global _whisper_model
    if _whisper_model is None:
        print("Loading Whisper model...")
        _whisper_model = whisper.load_model(WHISPER_MODEL)
    print("Transcribing...")
    result = _whisper_model.transcribe(path)
    return [
        {"timestamp": [round(s["start"], 3), round(s["end"], 3)], "text": s["text"]}
        for s in result["segments"]
    ]

def to_srt(data):
    srt = ""
    for i, item in enumerate(data, 1):
        start, end = item["timestamp"]
        srt += f"{i}\n{format_time(start)} --> {format_time(end)}\n{item['text'].strip()}\n\n"
    return srt

def run(text, voice=VOICE, speed=1.0):
    n = next_n()
    audio_path = os.path.join(AUDIO_DIR, f"audio_{n:03}.wav")
    srt_path = os.path.join(SUBTITLE_DIR, f"sub_{n:03}.srt")

    print("Generating audio...")
    generate_audio(text, voice, audio_path, speed)
    print(f"Audio saved to {audio_path}")

    data = transcribe(audio_path)

    srt = to_srt(data)
    with open(srt_path, "w") as f:
        f.write(srt)
    print(f"Subtitles saved to {srt_path}")
    return audio_path, srt_path

if __name__ == "__main__":
    text = TEXT.strip() or (sys.argv[1] if len(sys.argv) > 1 else input("Enter script text: "))
    run(text)
