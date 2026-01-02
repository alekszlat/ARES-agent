#!/usr/bin/env python3
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class PiperConfig:
    model_path: str
    host: str = "127.0.0.1"
    port: int = 5000
    # If True, you’ll see server logs in your terminal
    inherit_stdio: bool = True


class PiperTTS:
    def __init__(self, config: PiperConfig) -> None:
        self.config = config
        self.base_url = f"http://{config.host}:{config.port}"
        self._proc: Optional[subprocess.Popen] = None

        # Ensure we clean up if the program exits normally
        atexit.register(self.stop)

    def start(self) -> None:
        """Start Piper HTTP server if it isn't already running."""
        if self.is_running():
            return

        # If something is already serving that port, we consider it "running"
        if self._server_responds(timeout_s=0.5):
            return

        cmd = [
            sys.executable,
            "-m",
            "piper.http_server",
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
            "--model",
            self.config.model_path,
        ]

        stdout = None if self.config.inherit_stdio else subprocess.DEVNULL
        stderr = None if self.config.inherit_stdio else subprocess.DEVNULL

        self._proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
        self.wait_until_ready(timeout_s=10.0)

    def wait_until_ready(self, timeout_s: float = 10.0, poll_s: float = 0.2) -> None:
        """Wait until the HTTP server responds on its port."""
        deadline = time.time() + timeout_s
        last_err: Exception | None = None

        while time.time() < deadline:
            try:
                # Any HTTP response (even 404) means “server is alive”
                requests.get(self.base_url, timeout=1.0)
                return
            except Exception as e:
                last_err = e
                # If the server process crashed, fail fast with a helpful message
                if self._proc is not None and self._proc.poll() is not None:
                    raise RuntimeError("Piper server process exited unexpectedly.") from e
            time.sleep(poll_s)

        raise TimeoutError(f"Piper server not ready after {timeout_s}s. Last error: {last_err}")

    def speak(self, text: str) -> None:
        """Synthesize speech and play it."""
        # Start lazily (first time you speak)
        self.start()

        # Piper commonly accepts JSON {"text": "..."} at the base URL. :contentReference[oaicite:2]{index=2}
        r = requests.post(self.base_url, json={"text": text}, timeout=60)
        r.raise_for_status()

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(r.content)
                tmp_path = tmp.name

            self._play_wav(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def stop(self) -> None:
        """Stop the Piper server if we started it."""
        if self._proc is None:
            return

        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()

        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _server_responds(self, timeout_s: float) -> bool:
        try:
            requests.get(self.base_url, timeout=timeout_s)
            return True
        except Exception:
            return False

    def _play_wav(self, path: str) -> None:
        # Prefer a player that exists on the system
        for player in ("aplay", "pw-play", "paplay"):
            if shutil.which(player):
                subprocess.run([player, path], check=False)
                return
        raise RuntimeError("No audio player found (tried: aplay, pw-play, paplay).")


if __name__ == "__main__":
    tts = PiperTTS(PiperConfig(model_path="./models/en_GB-northern_english_male-medium.onnx"))
    tts.speak("Hello, this is Piper speaking.")
    tts.stop()
