from flask import Flask, jsonify, render_template_string, request, send_from_directory
import threading
import os
import pipeline
from pathlib import Path

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ShortTools</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101418;
      --panel: #182029;
      --panel-2: #22303d;
      --line: #314355;
      --text: #edf3f8;
      --muted: #9db0c2;
      --accent: #3fbf9a;
      --danger: #ff7b72;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #0f1419, #17202a 45%, #101418);
      color: var(--text);
    }
    main {
      max-width: 960px;
      margin: 0 auto;
      padding: 24px 16px 48px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 2rem;
    }
    p {
      color: var(--muted);
      margin: 0 0 18px;
    }
    .grid {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }
    .card {
      background: rgba(24, 32, 41, 0.92);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
    }
    label {
      display: block;
      margin: 12px 0 6px;
      font-size: 0.92rem;
      color: var(--muted);
    }
    textarea, select, input, button {
      width: 100%;
      font: inherit;
      border-radius: 10px;
      border: 1px solid var(--line);
    }
    textarea, select, input[type="file"] {
      background: var(--panel-2);
      color: var(--text);
      padding: 10px 12px;
    }
    textarea {
      min-height: 180px;
      resize: vertical;
    }
    input[type="range"] {
      accent-color: var(--accent);
    }
    button {
      background: var(--accent);
      color: #082018;
      font-weight: 700;
      padding: 11px 14px;
      cursor: pointer;
      margin-top: 14px;
    }
    button.secondary {
      background: transparent;
      color: var(--text);
    }
    button:disabled {
      opacity: 0.6;
      cursor: wait;
    }
    .row {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .row > * {
      flex: 1;
    }
    .status {
      min-height: 22px;
      margin-top: 10px;
      color: var(--muted);
    }
    .error { color: var(--danger); }
    .result {
      margin-top: 14px;
      display: none;
    }
    .result.show {
      display: block;
    }
    audio {
      width: 100%;
      margin: 12px 0;
    }
    pre {
      margin: 0;
      padding: 12px;
      border-radius: 12px;
      background: #0f1419;
      border: 1px solid var(--line);
      overflow: auto;
      white-space: pre-wrap;
    }
    ul {
      margin: 12px 0 0;
      padding-left: 18px;
      color: var(--muted);
    }
    li {
      margin: 6px 0;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <main>
    <h1>ShortTools</h1>
    <p>Generate voiceovers, preview voices, upload existing media, and export subtitles from one lightweight page.</p>

    <div class="grid">
      <section class="card">
        <h2>Generate</h2>
        <label for="voice">Voice</label>
        <div class="row">
          <select id="voice"></select>
          <button id="preview-btn" class="secondary" type="button">Preview</button>
        </div>

        <label for="speed">Speed <span id="speed-value">1.0</span></label>
        <input id="speed" type="range" min="0.7" max="1.3" step="0.05" value="1.0">

        <label for="script">Script</label>
        <textarea id="script" placeholder="Paste your script here"></textarea>

        <button id="generate-btn" type="button">Generate Audio + Subtitles</button>
        <div id="generate-status" class="status"></div>

        <div id="generate-result" class="result">
          <audio id="generated-audio" controls></audio>
          <pre id="generated-srt"></pre>
        </div>
      </section>

      <section class="card">
        <h2>Upload</h2>
        <label for="upload">Audio or Video File</label>
        <input id="upload" type="file" accept="audio/*,video/*">

        <button id="upload-btn" type="button">Transcribe Upload</button>
        <div id="upload-status" class="status"></div>

        <div id="upload-result" class="result">
          <audio id="uploaded-audio" controls></audio>
          <pre id="uploaded-srt"></pre>
        </div>
      </section>
    </div>

    <section class="card" style="margin-top:16px;">
      <h2>History</h2>
      <p>Click an item to reopen its audio and subtitle output.</p>
      <ul id="history-list"></ul>
    </section>
  </main>

  <script>
    const voiceEl = document.getElementById("voice");
    const speedEl = document.getElementById("speed");
    const speedValueEl = document.getElementById("speed-value");
    const historyEl = document.getElementById("history-list");

    function setStatus(id, message, isError = false) {
      const el = document.getElementById(id);
      el.textContent = message;
      el.className = isError ? "status error" : "status";
    }

    async function loadVoices() {
      const res = await fetch("/api/voices");
      const groups = await res.json();
      voiceEl.innerHTML = "";
      for (const [label, voices] of Object.entries(groups)) {
        const optgroup = document.createElement("optgroup");
        optgroup.label = label;
        for (const voice of voices) {
          const option = document.createElement("option");
          option.value = voice;
          option.textContent = voice;
          optgroup.appendChild(option);
        }
        voiceEl.appendChild(optgroup);
      }
    }

    async function loadHistory() {
      const res = await fetch("/api/files");
      const files = await res.json();
      historyEl.innerHTML = "";
      if (!files.length) {
        historyEl.innerHTML = "<li>No saved files yet.</li>";
        return;
      }
      for (const file of files.slice().reverse()) {
        const item = document.createElement("li");
        item.textContent = file.audio + (file.subtitle ? " | " + file.subtitle : "");
        item.addEventListener("click", async () => {
          document.getElementById("generated-audio").src = "/audio/" + file.audio + "?t=" + Date.now();
          document.getElementById("generate-result").classList.add("show");
          if (file.subtitle) {
            const subtitleRes = await fetch("/subtitles/" + file.subtitle + "?t=" + Date.now());
            document.getElementById("generated-srt").textContent = await subtitleRes.text();
          }
        });
        historyEl.appendChild(item);
      }
    }

    speedEl.addEventListener("input", () => {
      speedValueEl.textContent = speedEl.value;
    });

    document.getElementById("preview-btn").addEventListener("click", async () => {
      const res = await fetch("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice: voiceEl.value, speed: Number(speedEl.value) }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus("generate-status", data.error || "Preview failed", true);
        return;
      }
      const audio = new Audio("/previews/" + data.file + "?t=" + Date.now());
      audio.play();
      setStatus("generate-status", "Preview ready.");
    });

    document.getElementById("generate-btn").addEventListener("click", async () => {
      const text = document.getElementById("script").value.trim();
      if (!text) {
        setStatus("generate-status", "Enter a script first.", true);
        return;
      }
      setStatus("generate-status", "Generating...");
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: voiceEl.value, speed: Number(speedEl.value) }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus("generate-status", data.error || "Generation failed", true);
        return;
      }
      document.getElementById("generated-audio").src = "/audio/" + data.audio + "?t=" + Date.now();
      document.getElementById("generated-srt").textContent = data.srt;
      document.getElementById("generate-result").classList.add("show");
      setStatus("generate-status", "Saved " + data.audio);
      loadHistory();
    });

    document.getElementById("upload-btn").addEventListener("click", async () => {
      const file = document.getElementById("upload").files[0];
      if (!file) {
        setStatus("upload-status", "Choose a file first.", true);
        return;
      }
      setStatus("upload-status", "Transcribing...");
      const form = new FormData();
      form.append("audio", file);
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) {
        setStatus("upload-status", data.error || "Upload failed", true);
        return;
      }
      document.getElementById("uploaded-audio").src = "/audio/" + data.audio + "?t=" + Date.now();
      document.getElementById("uploaded-srt").textContent = data.srt;
      document.getElementById("upload-result").classList.add("show");
      setStatus("upload-status", "Saved " + data.audio);
      loadHistory();
    });

    loadVoices();
    loadHistory();
  </script>
</body>
</html>
"""

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
    return render_template_string(INDEX_HTML)


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
