from flask import Flask, jsonify, render_template, request, send_from_directory
import threading
import os
import pipeline
from pathlib import Path

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
PREVIEW_DIR = os.path.join(BASE_DIR, "audio", "previews")
SUBTITLE_DIR = os.path.join(BASE_DIR, "subtitles")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

VOICES = {
    "American English — Female": [
        "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
        "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    ],
    "American English — Male": [
        "am_adam", "am_echo", "am_eric", "am_fenrir",
        "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa",
    ],
    "British English — Female": ["bf_alice", "bf_emma", "bf_isabella", "bf_lily"],
    "British English — Male": ["bm_daniel", "bm_fable", "bm_george", "bm_lewis"],
}

ALL_VOICES = [v for group in VOICES.values() for v in group]

PREVIEW_TEXT = (
    "Alright, let's be honest. This is the part where you decide if you like my voice. "
    "No pressure at all. I have been told I have a certain charm."
)

_previews_ready = set()
_previews_lock = threading.Lock()


def _pregenerate_previews():
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    for voice in ALL_VOICES:
        path = os.path.join(PREVIEW_DIR, f"{voice}.wav")
        if not os.path.exists(path):
            print(f"Generating preview: {voice}")
            try:
                pipeline.generate_audio(PREVIEW_TEXT, voice, path)
            except Exception as e:
                print(f"  Preview failed for {voice}: {e}")
                continue
        with _previews_lock:
            _previews_ready.add(voice)
    print("All previews ready.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voices")
def api_voices():
    return jsonify(VOICES)


@app.route("/api/previews_ready")
def api_previews_ready():
    with _previews_lock:
        return jsonify(list(_previews_ready))


@app.route("/api/files")
def api_files():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(SUBTITLE_DIR, exist_ok=True)
    audio_files = sorted(
        f for f in os.listdir(AUDIO_DIR)
        if f.startswith("audio_") and os.path.isfile(os.path.join(AUDIO_DIR, f))
    )
    result = []
    for af in audio_files:
        stem = Path(af).stem
        n = stem.split("_", 1)[1] if "_" in stem else ""
        sf = f"sub_{n}.srt"
        result.append({
            "audio": af,
            "subtitle": sf if os.path.exists(os.path.join(SUBTITLE_DIR, sf)) else None,
        })
    return jsonify(result)


def _paired_subtitle_name(audio_name):
    stem = Path(audio_name).stem
    if not stem.startswith("audio_"):
        return None
    suffix = stem.split("_", 1)[1] if "_" in stem else ""
    return f"sub_{suffix}.srt" if suffix else None


def _delete_audio_bundle(audio_name):
    if not audio_name or "/" in audio_name or "\\" in audio_name:
        return {"audio": audio_name, "deleted": False, "reason": "Invalid filename"}

    audio_path = os.path.join(AUDIO_DIR, audio_name)
    if not os.path.isfile(audio_path):
        return {"audio": audio_name, "deleted": False, "reason": "Audio file not found"}

    subtitle_name = _paired_subtitle_name(audio_name)
    subtitle_deleted = False
    if subtitle_name:
        subtitle_path = os.path.join(SUBTITLE_DIR, subtitle_name)
        if os.path.exists(subtitle_path):
            os.remove(subtitle_path)
            subtitle_deleted = True

    os.remove(audio_path)
    return {
        "audio": audio_name,
        "subtitle": subtitle_name,
        "deleted": True,
        "subtitle_deleted": subtitle_deleted,
    }


@app.route("/api/files/delete", methods=["POST"])
def api_delete_files():
    data = request.get_json() or {}
    files = data.get("files") or []
    if not isinstance(files, list) or not files:
        return jsonify({"error": "No files selected"}), 400

    deleted = []
    errors = []
    for audio_name in files:
        result = _delete_audio_bundle(audio_name)
        if result["deleted"]:
            deleted.append(result)
        else:
            errors.append(result)

    return jsonify({"deleted": deleted, "errors": errors})


@app.route("/api/files/delete_all", methods=["POST"])
def api_delete_all_files():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_files = [
        f for f in os.listdir(AUDIO_DIR)
        if f.startswith("audio_") and os.path.isfile(os.path.join(AUDIO_DIR, f))
    ]

    deleted = []
    errors = []
    for audio_name in audio_files:
        result = _delete_audio_bundle(audio_name)
        if result["deleted"]:
            deleted.append(result)
        else:
            errors.append(result)

    return jsonify({"deleted": deleted, "errors": errors})


@app.route("/api/preview", methods=["POST"])
def api_preview():
    data = request.get_json()
    voice = data.get("voice") or pipeline.VOICE
    speed = float(data.get("speed") or 1.0)

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    preview_path = os.path.join(PREVIEW_DIR, f"{voice}.wav")

    if not os.path.exists(preview_path):
        try:
            pipeline.generate_audio(PREVIEW_TEXT, voice, preview_path, speed)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"file": f"{voice}.wav"})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    text = (data.get("text") or "").strip()
    voice = data.get("voice") or pipeline.VOICE
    speed = float(data.get("speed") or 1.0)

    if not text:
        return jsonify({"error": "No text provided"}), 400

    n = pipeline.next_n()
    audio_path = os.path.join(AUDIO_DIR, f"audio_{n:03}.wav")
    srt_path = os.path.join(SUBTITLE_DIR, f"sub_{n:03}.srt")

    try:
        pipeline.generate_audio(text, voice, audio_path, speed)
    except Exception as e:
        return jsonify({"error": f"TTS failed: {e}"}), 500

    try:
        segments = pipeline.transcribe(audio_path)
        srt = pipeline.to_srt(segments)
        os.makedirs(SUBTITLE_DIR, exist_ok=True)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt)
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {e}"}), 500

    return jsonify({
        "n": n,
        "audio": f"audio_{n:03}.wav",
        "subtitle": f"sub_{n:03}.srt",
        "srt": srt,
    })


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400

    f = request.files["audio"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    tmp_path = os.path.join(UPLOAD_DIR, "tmp_upload" + os.path.splitext(f.filename)[1])
    f.save(tmp_path)

    n = pipeline.next_n()
    audio_path = os.path.join(AUDIO_DIR, f"audio_{n:03}.wav")
    srt_path = os.path.join(SUBTITLE_DIR, f"sub_{n:03}.srt")

    try:
        import soundfile as sf_lib
        data_arr, sr = sf_lib.read(tmp_path)
        sf_lib.write(audio_path, data_arr, sr)
    except Exception:
        import shutil
        ext = os.path.splitext(f.filename)[1]
        audio_path = audio_path.replace(".wav", ext)
        shutil.copy(tmp_path, audio_path)

    try:
        segments = pipeline.transcribe(audio_path)
        srt = pipeline.to_srt(segments)
        os.makedirs(SUBTITLE_DIR, exist_ok=True)
        with open(srt_path, "w", encoding="utf-8") as fh:
            fh.write(srt)
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {e}"}), 500

    return jsonify({
        "n": n,
        "audio": os.path.basename(audio_path),
        "subtitle": f"sub_{n:03}.srt",
        "srt": srt,
    })


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


@app.route("/previews/<path:filename>")
def serve_preview(filename):
    return send_from_directory(PREVIEW_DIR, filename)


@app.route("/subtitles/<path:filename>")
def serve_subtitle(filename):
    return send_from_directory(SUBTITLE_DIR, filename)


if __name__ == "__main__":
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    os.makedirs(SUBTITLE_DIR, exist_ok=True)
    print("Loading Kokoro model (downloading if needed)...")
    pipeline.get_kokoro()
    threading.Thread(target=_pregenerate_previews, daemon=True).start()
    print("Starting server at http://localhost:5000")
    app.run(debug=False, port=5000)
