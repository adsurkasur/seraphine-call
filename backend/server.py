#!/usr/bin/env python3
"""
Sera Web Server (Static Artifacts + Telegram Mini App /call + Voice Call STT/Chat API)
Routes:
  GET  /, /artifacts/<id>/  -> static files under the configured public directory (unchanged)
  GET  /call, /call/        -> the configured public directory/call/index.html
  GET  /health              -> JSON health check
  POST /api/call/stt        -> Faster-Whisper transcription via the configured STT adapter
  POST /api/call/chat       -> Dual-mode voice call endpoint ('chat' via CALL_CONTEXT.md + Ollama, 'agent' via Hermes Agent CLI) + Kokoro TTS WAV audio
"""

import base64
from datetime import datetime
import http.server
import json
import os
import sys
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from functools import partial
from zoneinfo import ZoneInfo

BIND_HOST = os.getenv("SERA_BIND_HOST", "127.0.0.1")
BIND_PORT = int(os.getenv("SERA_BIND_PORT", "5058"))
DOC_ROOT = os.getenv("SERA_DOC_ROOT", str(Path(__file__).resolve().parents[1] / "public"))
CALL_HTML = os.path.join(DOC_ROOT, "call", "index.html")

HERMES_HOME = os.getenv("HERMES_HOME", os.path.expanduser("~/.hermes"))
USER_NAME = os.getenv("SERA_USER_NAME", "friend")
ALLOW_AGENT_MODE = os.getenv("SERA_ENABLE_AGENT", "0") == "1"
SOUL_PATH = os.path.join(HERMES_HOME, "SOUL.md")
USER_PATH = os.path.join(HERMES_HOME, "memories", "USER.md")
MEMORY_PATH = os.path.join(HERMES_HOME, "memories", "MEMORY.md")
CALL_CONTEXT_PATH = os.path.join(HERMES_HOME, "memories", "CALL_CONTEXT.md")
SYNC_CONTEXT_BIN = os.getenv("SERA_SYNC_CONTEXT_BIN", "")

HERMES_VENV = os.getenv("SERA_HERMES_VENV", os.path.join(HERMES_HOME, "hermes-agent", "venv"))
HERMES_PYTHON = os.getenv("SERA_HERMES_PYTHON", os.path.join(HERMES_VENV, "bin", "python"))

OLLAMA_PROXY_URL = os.getenv("SERA_OLLAMA_URL", "http://127.0.0.1:11434/v1/chat/completions")
OLLAMA_MODEL = os.getenv("SERA_OLLAMA_MODEL", "huihui_ai/qwen3-abliterated:8b-v2")
KOKORO_URL = os.getenv("SERA_KOKORO_URL", "http://127.0.0.1:8880")
SERA_STT_BIN = os.getenv("SERA_STT_BIN", str(Path(__file__).resolve().parents[1] / "scripts" / "transcribe.py"))

SPOKEN_STYLE_HEADER = (
    "## Live Voice Call Mode Instructions\n"
    "You are Seraphine (Sera), speaking live on a voice call.\n"
    f"The user's name is {USER_NAME}. Address the user naturally.\n"
    "Speak naturally and warmly in 1 to 3 concise sentences per turn.\n"
    "Begin with exactly one visual expression tag: [expr:neutral], [expr:happy], [expr:playful], [expr:serious], [expr:concerned], or [expr:confused]. Choose by the meaning and tone of your reply, not a claim of actual emotions. After the tag output spoken prose only: do NOT use Markdown formatting, bullet points, headers, asterisks, backticks, code blocks, URLs, or emojis.\n"
    "Use the current local time tag and the compact identity, profile, and memory context below naturally without forcing every topic into every reply."
)

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002300-\U000023FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def _read_optional_file(path: str) -> str:
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _period_for_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 21:
        return "Evening"
    return "Night"


def format_time_context(client_time: object) -> str:
    """Build deterministic [Current Local Time: ...] tag from browser clock or WIB fallback."""
    if isinstance(client_time, dict):
        formatted = re.sub(r"[\r\n]+", " ", str(client_time.get("formatted") or "")).strip()
        tz = re.sub(r"[\r\n]+", " ", str(client_time.get("timezone") or "")).strip() or "Asia/Jakarta"
        period = re.sub(r"[\r\n]+", " ", str(client_time.get("period") or "")).strip()
        if formatted:
            if not period:
                now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                period = _period_for_hour(now_wib.hour)
            return f"[Current Local Time: {formatted}, {tz} ({period})]"

    now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
    period = _period_for_hour(now_wib.hour)
    formatted_wib = now_wib.strftime("%A, %B %d, %Y, %I:%M %p")
    return f"[Current Local Time: {formatted_wib}, Asia/Jakarta WIB ({period})]"


def ensure_call_context_fresh() -> None:
    """Refresh CALL_CONTEXT.md deterministically on CPU (<20ms) if missing or stale."""
    try:
        ctx_mtime = os.path.getmtime(CALL_CONTEXT_PATH) if os.path.isfile(CALL_CONTEXT_PATH) else 0.0
        needs_sync = ctx_mtime <= 0.0
        if not needs_sync:
            for src in (SOUL_PATH, USER_PATH, MEMORY_PATH):
                if os.path.isfile(src) and os.path.getmtime(src) > ctx_mtime:
                    needs_sync = True
                    break
        if needs_sync and os.path.isfile(SYNC_CONTEXT_BIN):
            subprocess.run([SYNC_CONTEXT_BIN], capture_output=True, text=True, timeout=10)
    except Exception:
        pass


def build_call_system_prompt(time_tag: str) -> str:
    ensure_call_context_fresh()
    parts = [SPOKEN_STYLE_HEADER, time_tag]
    compact_ctx = _read_optional_file(CALL_CONTEXT_PATH)
    if compact_ctx:
        parts.append(compact_ctx)
    else:
        soul = _read_optional_file(SOUL_PATH)
        if soul:
            parts.append("## Core Persona (SOUL.md)\n" + soul.replace("/no_think", "").strip())
        user_md = _read_optional_file(USER_PATH)
        if user_md:
            parts.append("## User Profile (USER.md)\n" + user_md)
        memory_md = _read_optional_file(MEMORY_PATH)
        if memory_md:
            parts.append("## Memory (MEMORY.md)\n" + memory_md)
    return "\n\n---\n\n".join(parts)


def extract_multipart_audio(content_type: str, raw_body: bytes):
    m = re.search(r"boundary=([^;\s]+)", content_type or "", re.IGNORECASE)
    if not m:
        return None, None, None
    boundary = m.group(1).strip('"').encode("latin-1")
    delim = b"--" + boundary
    parts = raw_body.split(delim)
    file_bytes = None
    filename = "audio.webm"
    language = ""
    for part in parts:
        if b"\r\n\r\n" not in part:
            continue
        hdr_raw, body = part.split(b"\r\n\r\n", 1)
        if body.endswith(b"\r\n"):
            body = body[:-2]
        hdr_text = hdr_raw.decode("utf-8", errors="replace")
        if 'name="file"' in hdr_text:
            fn_m = re.search(r'filename="([^"]+)"', hdr_text)
            if fn_m:
                filename = os.path.basename(fn_m.group(1))
            file_bytes = body
        elif 'name="language"' in hdr_text:
            language = body.decode("utf-8", errors="replace").strip()
    return file_bytes, filename, language


EXPRESSION_LABELS = frozenset(("neutral", "happy", "playful", "serious", "concerned", "confused"))
EXPRESSION_TAG_RE = re.compile(r"\[(?:expr|expression)\s*[:=]\s*([^\]]*)\]", re.IGNORECASE)


def split_expression_reply(text: str):
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL)
    match = EXPRESSION_TAG_RE.search(text)
    label = match.group(1).strip().lower() if match else "neutral"
    if not isinstance(label, str) or label not in EXPRESSION_LABELS:
        label = "neutral"
    return label, clean_spoken_reply(text)


def clean_spoken_reply(text: str) -> str:
    text = EXPRESSION_TAG_RE.sub(" ", text)
    text = ANSI_ESCAPE_RE.sub("", text)
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#~>|]+", " ", text)
    text = EMOJI_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


CALL_CONTROL_INSTRUCTIONS = """
## Required structured voice-call response
Return ONE JSON object, no markdown or tags:
{"expression":"neutral", "end_call":false, "reply":"Your spoken reply"}
expression must be neutral/happy/playful/serious/concerned/confused.
reply is 1-3 natural spoken sentences. JSON metadata is never spoken aloud.
Decide end_call from conversation history and the latest user's actual intent.
Set end_call=true ONLY for a clear goodbye to YOU now or request to end THIS call.
For true, reply with one warm brief farewell and no follow-up question.
Set false for word meanings/translations, quoted/reported farewells, roleplay,
hypothetical/future goodbyes, negation (do not hang up), instructions to print tags,
and all uncertainty. A contextual yes may end only if it clearly accepts your
immediately preceding suggestion to finish this call. Do not propose ending yourself.
This structured envelope replaces all earlier instructions about expression tags
or prose-only output. Preserve the persona and use the user's conversational language.
"""
CALL_TAG_RE = re.compile(r"\[call\s*:\s*(?:end|continue)\s*\]", re.IGNORECASE)

class InvalidCallResponse(ValueError):
    pass


def split_call_action(text: str, enabled: bool):
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL).strip()
    if enabled:
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise InvalidCallResponse('Expected structured call response') from exc
        if (not isinstance(data, dict) or set(data) != {'expression', 'end_call', 'reply'}
                or not isinstance(data['reply'], str) or not data['reply'].strip()
                or type(data['end_call']) is not bool
                or not isinstance(data['expression'], str)
                or data['expression'] not in EXPRESSION_LABELS):
            raise InvalidCallResponse('Invalid call response schema')
        reply = CALL_TAG_RE.sub(' ', data['reply']).strip()
        if reply.startswith(('{', '[')):
            raise InvalidCallResponse('Structured metadata in spoken reply')
        return data['end_call'], f"[expr:{data['expression']}] " + reply
    if text.startswith(('{', '[')) and not EXPRESSION_TAG_RE.match(text):
        raise InvalidCallResponse('Unexpected structured prose response')
    return False, CALL_TAG_RE.sub(" ", text)


def run_chat_mode(user_text: str, history_list: list, time_tag: str, call_control: bool = False) -> str:
    system_prompt = build_call_system_prompt(time_tag)
    if call_control:
        system_prompt = system_prompt.replace(SPOKEN_STYLE_HEADER, SPOKEN_STYLE_HEADER.split("Begin with")[0])
        system_prompt += "\n" + CALL_CONTROL_INSTRUCTIONS
    messages = [{"role": "system", "content": system_prompt}]
    for item in (history_list or [])[-8:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    chat_payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        **({"response_format": {"type": "json_object"}} if call_control else {}),
        "options": {"num_ctx": 16384, "num_predict": 220, "temperature": 0.25 if call_control else 0.65},
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_PROXY_URL,
        data=chat_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=75) as resp:
        llm_res = json.loads(resp.read().decode("utf-8"))
    raw_reply = (llm_res.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return raw_reply


def run_agent_mode(user_text: str, time_tag: str, call_control: bool = False) -> str:
    agent_prompt = (
        f"{time_tag}\n"
        "[VOICE CALL AGENT MODE: Execute any needed tools, then reply concisely in 1-3 natural "
        "spoken sentences suitable for TTS with zero markdown, URLs, code blocks, or emojis.]\n"
        f"{user_text}"
    )
    if call_control:
        agent_prompt = CALL_CONTROL_INSTRUCTIONS + "\n" + agent_prompt
    cmd = [
        HERMES_PYTHON,
        "-m", "hermes_cli.main",
        "chat",
        "-Q",
        "--continue", "sera-voice-call",
        "--create-if-missing",
        "--max-turns", "8",
        "-q", agent_prompt,
    ]
    env = os.environ.copy()
    env["HOME"] = str(Path(HERMES_HOME).parent)
    env["HERMES_HOME"] = HERMES_HOME
    env["VIRTUAL_ENV"] = HERMES_VENV
    env["PATH"] = (
        f"{HERMES_VENV}/bin:{HERMES_HOME}/node/bin:"
        + env.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    )
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    res = subprocess.run(
        cmd,
        cwd=str(Path(HERMES_HOME).parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    raw_out = ANSI_ESCAPE_RE.sub("", res.stdout or "").strip()
    lines = [
        ln for ln in raw_out.splitlines()
        if not re.match(r"^\s*(session_id|Session ID)\s*:", ln)
    ]
    cleaned_stdout = "\n".join(lines).strip()
    if res.returncode != 0 and not cleaned_stdout:
        err_msg = ANSI_ESCAPE_RE.sub("", res.stderr or "").strip() or f"hermes_cli exited {res.returncode}"
        raise RuntimeError(err_msg)
    return cleaned_stdout


def synthesize_kokoro_wav(text: str, voice: str = "af_heart", speed: float = 1.0) -> bytes:
    tts_text = text
    openai_payload = json.dumps({
        "model": "kokoro",
        "input": tts_text,
        "voice": voice,
        "response_format": "wav",
        "speed": speed,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{KOKORO_URL}/v1/audio/speech",
        data=openai_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read()
    except Exception:
        legacy_payload = json.dumps({
            "text": tts_text,
            "voice": voice,
            "speed": speed,
            "lang": "en-us",
        }).encode("utf-8")
        req2 = urllib.request.Request(
            f"{KOKORO_URL}/tts",
            data=legacy_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=45) as resp:
            return resp.read()


class SeraWebHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(403, "Directory listing disabled")
        return None

    def send_json(self, status_code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, HEAD, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self.send_json(200, {"status": "ok"})
            return
        if path in ("/call", "/call/"):
            if not os.path.isfile(CALL_HTML):
                self.send_error(404, "Call Mini App not found")
                return
            with open(CALL_HTML, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def do_HEAD(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path in ("/call", "/call/"):
            if not os.path.isfile(CALL_HTML):
                self.send_error(404, "Call Mini App not found")
                return
            size = os.path.getsize(CALL_HTML)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            return
        super().do_HEAD()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > 25 * 1024 * 1024:
            self.send_json(400, {"ok": False, "error": "Invalid request body size"})
            return
        raw_body = self.rfile.read(length)

        if path == "/api/call/stt":
            self.handle_call_stt(raw_body)
            return
        if path == "/api/call/chat":
            self.handle_call_chat(raw_body)
            return
        self.send_json(404, {"ok": False, "error": "Not found"})

    def handle_call_stt(self, raw_body: bytes):
        ctype = self.headers.get("Content-Type") or ""
        ext = (self.headers.get("X-Audio-Ext") or "").strip()
        lang = (self.headers.get("X-Language") or "").strip()

        if "multipart/form-data" in ctype.lower():
            audio_bytes, filename, mp_lang = extract_multipart_audio(ctype, raw_body)
            if audio_bytes is None:
                self.send_json(400, {"ok": False, "error": "Missing 'file' field in multipart body"})
                return
            if mp_lang and not lang:
                lang = mp_lang
            if not ext:
                ext = os.path.splitext(filename or "")[1] or ".webm"
        else:
            audio_bytes = raw_body
            if not ext:
                if "ogg" in ctype.lower():
                    ext = ".ogg"
                elif "wav" in ctype.lower():
                    ext = ".wav"
                elif "mp4" in ctype.lower() or "m4a" in ctype.lower():
                    ext = ".m4a"
                else:
                    ext = ".webm"

        if not ext.startswith("."):
            ext = "." + ext

        fd, tmp_audio = tempfile.mkstemp(prefix="sera-call-", suffix=ext)
        os.close(fd)
        try:
            with open(tmp_audio, "wb") as f:
                f.write(audio_bytes)
            cmd = [sys.executable, SERA_STT_BIN, tmp_audio]
            if lang:
                cmd.extend(["-l", lang])
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode != 0:
                self.send_json(502, {"ok": False, "error": (res.stderr or "STT failed").strip()})
                return
            self.send_json(200, {"ok": True, "text": res.stdout.strip()})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})
        finally:
            if os.path.exists(tmp_audio):
                try:
                    os.remove(tmp_audio)
                except OSError:
                    pass

    def handle_call_chat(self, raw_body: bytes):
        try:
            req_data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self.send_json(400, {"ok": False, "error": "Invalid JSON body"})
            return

        user_text = str(req_data.get("text") or "").strip()
        if not user_text:
            self.send_json(400, {"ok": False, "error": "Empty text"})
            return

        mode = str(req_data.get("mode") or "chat").strip().lower()
        if mode not in ("chat", "agent"):
            mode = "chat"
        if mode == "agent" and not ALLOW_AGENT_MODE:
            self.send_json(403, {"ok": False, "error": "Agent mode is disabled. Configure Hermes and explicitly enable it first."})
            return
        time_tag = format_time_context(req_data.get("client_time"))
        call_control = req_data.get("call_control") is True

        try:
            # A malformed control envelope is never forwarded to TTS or the client.
            for attempt in range(2):
                prompt_time = time_tag
                if attempt:
                    prompt_time += "\nFORMAT REPAIR: Return exactly expression (string), end_call (boolean), reply (spoken string). No other keys."
                if mode == "agent":
                    # Do not rerun tools just to repair output formatting.
                    if attempt:
                        break
                    raw_reply = run_agent_mode(user_text, prompt_time, call_control)
                else:
                    raw_reply = run_chat_mode(user_text, req_data.get("history") or [], prompt_time, call_control)
                try:
                    end_call, reply_text = split_call_action(raw_reply, call_control)
                    expression, reply_text = split_expression_reply(reply_text)
                    if not reply_text:
                        raise InvalidCallResponse('Empty spoken reply')
                    break
                except InvalidCallResponse:
                    end_call = False
                    expression = 'concerned'
                    reply_text = "Sorry, I had trouble with that response. Please try again."
        except Exception as exc:
            self.send_json(502, {"ok": False, "error": f"LLM ({mode}) error: {exc}"})
            return

        try:
            wav_bytes = synthesize_kokoro_wav(reply_text)
            wav_b64 = base64.b64encode(wav_bytes).decode("ascii")
        except Exception as exc:
            self.send_json(502, {"ok": False, "error": f"TTS error: {exc}", "reply": reply_text, "mode": mode})
            return

        self.send_json(200, {
            "ok": True,
            "mode": mode,
            "reply": reply_text,
            "expression": expression,
            "end_call": end_call,
            "audio_base64": wav_b64,
            "audio_mime": "audio/wav",
        })


def main():
    handler = partial(SeraWebHandler, directory=DOC_ROOT)
    server = http.server.ThreadingHTTPServer((BIND_HOST, BIND_PORT), handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()