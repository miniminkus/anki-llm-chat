"""Streaming API client for OpenRouter and Ollama backends.

Uses only stdlib (urllib) so the add-on has no bundled dependencies.
Streaming is handled in a QThread to keep the UI responsive.
"""

import json
import socket
import urllib.request
import urllib.error

from aqt.qt import QThread, pyqtSignal

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class StreamWorker(QThread):
    """Background thread that streams chat completions via SSE."""

    chunk_received = pyqtSignal(str)
    stream_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, model, messages, max_tokens=1024, temperature=0.7,
                 provider="openrouter", ollama_url="http://localhost:11434"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.messages = messages
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.provider = provider
        self.ollama_url = ollama_url.rstrip("/")
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        if self.provider == "openrouter" and not self.api_key:
            self.error_occurred.emit(
                "API key not set. Open settings (\u2699) to configure."
            )
            return

        payload = json.dumps({
            "model": self.model,
            "messages": self.messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }).encode("utf-8")

        if self.provider == "ollama":
            url = f"{self.ollama_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
        else:
            url = OPENROUTER_API_URL
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/anki-card-assistant",
                "X-Title": "Card Assistant",
            }

        req = urllib.request.Request(url, data=payload, headers=headers)

        full_response = ""
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw_line in resp:
                    if self._cancelled:
                        break

                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                        content = (
                            chunk["choices"][0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if content:
                            full_response += content
                            self.chunk_received.emit(content)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        except urllib.error.HTTPError as e:
            self.error_occurred.emit(_read_api_error(e))
            return
        except (urllib.error.URLError, socket.timeout) as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, socket.gaierror):
                self.error_occurred.emit("No internet connection.")
            elif isinstance(reason, socket.timeout):
                self.error_occurred.emit("Request timed out.")
            else:
                self.error_occurred.emit(f"Connection error: {reason}")
            return
        except Exception as e:
            self.error_occurred.emit(str(e))
            return

        self.stream_finished.emit(full_response)


def fetch_models(api_key, provider="openrouter", ollama_url="http://localhost:11434"):
    """Fetch available model IDs. Returns a sorted list."""
    ollama_url = ollama_url.rstrip("/")

    if provider == "ollama":
        req = urllib.request.Request(f"{ollama_url}/api/tags")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return sorted(m["name"] for m in data.get("models", []))
        except Exception:
            return []
    else:
        if not api_key:
            return []
        req = urllib.request.Request(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return sorted(m["id"] for m in data.get("data", []))
        except Exception:
            return []


def test_connection(api_key, provider="openrouter", ollama_url="http://localhost:11434",
                    model=""):
    """Test connectivity to the selected provider. Returns (ok, message).

    If *model* is given, sends a tiny chat completion to verify the key
    actually works with that model.  Otherwise falls back to listing models.
    """
    ollama_url = ollama_url.rstrip("/")

    try:
        if model:
            # Send a minimal completion request to validate key + model
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 1,
                "temperature": 0,
                "stream": False,
            }).encode("utf-8")

            if provider == "ollama":
                url = f"{ollama_url}/v1/chat/completions"
                headers = {"Content-Type": "application/json"}
            else:
                if not api_key:
                    return False, "API key is empty"
                url = OPENROUTER_API_URL
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/anki-card-assistant",
                    "X-Title": "Card Assistant",
                }

            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                json.loads(resp.read().decode("utf-8"))
                return True, f"Connected \u2014 {model} is working"
        else:
            # No model selected — just check basic connectivity
            if provider == "ollama":
                req = urllib.request.Request(f"{ollama_url}/api/tags")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    count = len(data.get("models", []))
                    return True, f"Connected \u2014 {count} model(s) available"
            else:
                if not api_key:
                    return False, "API key is empty"
                req = urllib.request.Request(
                    OPENROUTER_MODELS_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    count = len(data.get("data", []))
                    return True, f"Connected \u2014 {count} model(s) available"
    except urllib.error.HTTPError as e:
        return False, _read_api_error(e)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        return False, f"Connection failed: {reason}"
    except socket.timeout:
        return False, "Connection timed out"
    except Exception as e:
        return False, str(e)


def _read_api_error(e):
    """Extract the error message from an API HTTP error response."""
    try:
        body = e.read().decode("utf-8", errors="replace")
    except Exception:
        return f"HTTP {e.code}"

    try:
        data = json.loads(body)
        err = data.get("error", {})
        if isinstance(err, dict) and err.get("message"):
            return f"{err['message']} ({e.code})"
        if isinstance(data, dict) and data.get("message"):
            return f"{data['message']} ({e.code})"
    except (json.JSONDecodeError, AttributeError):
        pass

    preview = body.strip()[:200]
    return f"HTTP {e.code}: {preview}" if preview else f"HTTP {e.code}"
