# Seraphine Call

A lightweight, single-character voice companion with a whole-PNG avatar, audio-driven mouth and blink states, microphone interruption, Kokoro speech, and an Ollama-backed conversation API. Includes the current chibi artwork and the structured-response leak fix.

## What is included

- Plain HTML/CSS/JavaScript `/call`; no frontend build step.
- Seven prepared PNG states, one whole frame at a time. No Live2D, runtime body cutouts, artwork generation, or automatic rigging.
- Green mic / blue Sera speech button with audio scale and glow, quiet-call breathing, audio ring, thinking-only rotation/wave, reduced-motion support.
- Local STT adapter, chat API, optional Hermes Agent integration, structured farewell actions and playback-completion hangup.
- Settings sheet, procedural UI cues, pre-generated reusable hearing-fallback WAV, and sleeping end state.

This is a sanitized release snapshot. It intentionally excludes private persona/memories, conversation recordings, secrets, machine-specific wake-on-LAN/SSH scripts, deployment backups, old artwork and historical model projects. The original private workspace is not this public repository.

## Prerequisites

Python 3.11+, curl, and separately running services:

1. An OpenAI-compatible Ollama chat endpoint with your chosen model.
2. Kokoro with `/v1/audio/speech` (legacy `/tts` fallback supported).
3. A Whisper-compatible `/v1/audio/transcriptions` service accepting multipart `file`, `model` and optional `language`.

No models, model weights, Hermes installation, or third-party service runtimes are bundled. Browser Auto STT is optional; server STT is the fallback. Microphone access needs localhost or HTTPS. The server defaults to loopback and provides no standalone authentication; retain your authenticated reverse proxy before exposing it outside a trusted local environment.

## Run on Linux

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env for your own endpoints. Never commit it.
set -a
. ./.env
set +a
python backend/server.py
```

Open `http://127.0.0.1:5058/call/`. `/health` is the health check. Configure the service endpoints before testing a real call. The checked-in `.env.example` contains loopback examples, not the original operator's addresses.

The server reads environment variables; it does not automatically load `.env`. On Windows, use the equivalent virtual environment activation and set environment variables before starting Python. `tzdata` supplies timezone data where the OS does not.

## Configuration

See `.env.example`. `SERA_DOC_ROOT` defaults to this repository's `public/`; `SERA_STT_BIN` defaults to `scripts/transcribe.py`. Set `SERA_USER_NAME` for your own installation.

Optional private identity files are read from `HERMES_HOME`: `SOUL.md`, `memories/USER.md`, `memories/MEMORY.md`, or compact `memories/CALL_CONTEXT.md`. None are distributed. `context-examples/SOUL.example.md` is a generic template; keep actual context outside the public web directory and outside Git. Context refresh only runs if explicitly configured with `SERA_SYNC_CONTEXT_BIN`.

Agent mode is **disabled by default**. Enable `SERA_ENABLE_AGENT=1` only after setting up Hermes and the intended tool permissions under the service account. The public example does not use an automatic `--yolo` flag. Chat mode requires no Hermes CLI. See `deploy/seraphine-call.service.example` for an optional Linux service template; adapt paths/user and protect its EnvironmentFile. The repository does not install or restart services automatically.

## Farewell control and response safety

The frontend sends `call_control:true`. The model must return exactly `expression` (supported string), `end_call` (boolean), and `reply` (spoken string). The server validates this before TTS. Malformed output gets one chat-format repair; repeated failure becomes safe prose and `end_call:false`. Agent tools are not rerun to repair formatting. Raw JSON/control metadata is never an acceptable spoken response.

A clear goodbye can schedule hangup **after natural playback completion**. Interrupting speech cancels it. Playback errors and missing audio do not hang up. Definition questions, quoted or uncertain goodbyes should continue. Intent remains model-dependent; validation prevents protocol leakage, not every possible semantic mistake.

## Tests

```sh
python tests/test_call_response.py
python tests/test_stt_adapter.py
```

These use fixtures/mocks and do not call a model, microphones, or paid services. See `VERIFICATION.md` for what was checked on the originating deployment and what still needs device-specific testing.

## Artwork and motion

Assets are in `public/assets/manual-ready-v1/manifest.json`. Other requested expressions fall back to neutral. Sprite switching uses a 45ms whole-frame opacity transition; there is no avatar geometry animation. Independent frames are not mathematically pixel-locked. Call-button breathing and canvas motion do not deform Sera. Proposed upper-body sway is documented in `MOTION_ROADMAP.md` and is not implemented.

## License

Apache License 2.0: see [LICENSE](LICENSE) and [NOTICE](NOTICE). Included project-owned contributions and supplied artwork are released with this repository. External services, model weights and dependencies retain their own licenses. Lucide-derived icon paths carry the notice in `THIRD_PARTY_LICENSES/lucide.txt`. No third-party model is relicensed by this project.
