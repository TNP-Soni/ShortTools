# ShortTools

Small tools for creating short-form video assets with Kokoro TTS, Whisper transcription, and a simple Flask UI.

## What it does

- Generates narration audio from text
- Creates `.srt` subtitles from generated audio
- Serves a small web app for voice previews and file management

## Main files

- `app.py` - Flask app for the browser UI
- `pipeline.py` - audio generation and subtitle pipeline

## Run

```bash
pip install flask kokoro-onnx soundfile openai-whisper
python app.py
```
