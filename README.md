# ShortTools

Small Flask app for creating short-form voiceovers and subtitles with Kokoro TTS and Whisper.

## What it does

- Generates narration audio from text
- Creates `.srt` subtitles from generated or uploaded audio
- Serves a lightweight browser UI from `app.py`

## Main files

- `app.py` - Flask app for the browser UI
- `pipeline.py` - audio generation and subtitle pipeline

## Run

```bash
pip install flask kokoro-onnx soundfile openai-whisper
python app.py
```

The model files are downloaded automatically on first run and are intentionally not stored in the repo.
