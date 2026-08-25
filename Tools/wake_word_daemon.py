"""Zenith Wake-Word Daemon — always-listening "Zenith" (fully local).

Runs as a background thread inside the agent. Uses openWakeWord if available;
falls back to a push-key trigger (Ctrl+Alt+Z via the `keyboard` lib) when the
model/library is missing — so presence NEVER silently disappears.

On detection it writes data/wake_rescue.flag which:
  - revives a STUCK session instantly (Watchdog honors it), or
  - launches the agent console when nothing is running.
"""

import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

RESCUE_FLAG = Path("data/wake_rescue.flag")
AGENT_DIR = Path(__file__).resolve().parent.parent


def raise_rescue():
    RESCUE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    RESCUE_FLAG.write_text(datetime.now().isoformat(), encoding="utf-8")


def rescue_requested() -> bool:
    return RESCUE_FLAG.exists()


def clear_rescue():
    try:
        RESCUE_FLAG.unlink()
    except FileNotFoundError:
        pass


def _chime():
    try:
        import winsound
        winsound.Beep(880, 90)
        winsound.Beep(1320, 110)
    except Exception:
        pass


# ------------------------------------------------------- openWakeWord path --

def _oww_loop(stop_event: threading.Event):
    """Real wake-word loop using openWakeWord with a 'zenith' custom model if
    present, else built-in 'alexa' as stand-in until user trains theirs."""
    try:
        import numpy as np
        import sounddevice as sd
        from openwakeword.model import Model
    except Exception as e:
        logger.info(f"[wake] openWakeWord unavailable ({e}); falling back to hotkey mode")
        return False

    keywords = [k for k in ("zenith", "jarvis") ]
    models = []
    m = Model(wakeword_models=keywords, inference_framework="onnx") \
        if keywords else Model()
    models.append(m)

    CHUNK = 1280          # 80ms @16k
    RATE = 16000
    THRESHOLD = float(os.getenv("ZENITH_WAKE_THRESHOLD", "0.5"))
    REFRACTORY = 6.0      # seconds between triggers
    last = 0.0

    def callback(indata, frames, t_, status):
        nonlocal last
        if stop_event.is_set():
            raise sd.CallbackStop
        mono = indata[:, 0]
        try:
            preds = m.predict(mono)
            score = max(preds.values()) if preds else 0.0
            now = time.time()
            if score >= THRESHOLD and (now - last) > REFRACTORY:
                last = now
                logger.info(f"[wake] ZENITH detected (score={score:.2f}) → rescue flag")
                _chime()
                raise_rescue()
        except sd.CallbackStop:
            raise
        except Exception:
            pass

    with sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                        blocksize=CHUNK, callback=callback):
        logger.info("[wake] openWakeWord listening for 'Zenith'…")
        while not stop_event.is_set():
            time.sleep(0.2)
    return True


def _hotkey_loop(stop_event: threading.Event):
    """Fallback: Ctrl+Alt+Z raises the same rescue flag."""
    try:
        import keyboard
    except Exception as e:
        logger.warning(f"[wake] hotkey fallback unavailable ({e}); daemon idle")
        return True   # still "handled" so outer thread rests

    logger.info("[wake] fallback armed: Ctrl+Alt+Z = 'Zenith'")
    while not stop_event.is_set():
        try:
            keyboard.wait("ctrl+alt+z")
            time.sleep(0.3)                       # debounce
            if stop_event.is_set():
                break
            _chime()
            raise_rescue()
            logger.info("[wake] hotkey rescue raised")
        except Exception:
            time.sleep(1)
    return True


class WakeWordDaemon:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.mode = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return self.mode or "off"
        self.stop_event.clear()

        result = {}

        def runner():
            try:
                ok = _oww_loop(self.stop_event)
                result["mode"] = "openwakeword" if ok else "hotkey"
            except Exception as e:
                logger.debug(f"[wake] oww crashed: {e}")
                result["mode"] = "hotkey"
            if result["mode"] == "hotkey" and not self.stop_event.is_set():
                try:
                    _hotkey_loop(self.stop_event)
                except Exception as e:
                    logger.warning(f"[wake] hotkey loop failed: {e}")

        self.thread = threading.Thread(target=runner, daemon=True,
                                       name="ZenithWakeWord")
        self.thread.start()
        # give it a beat to decide mode
        time.sleep(0.5)
        self.mode = result.get("mode", "starting")
        return self.mode

    def status(self) -> str:
        if not self.thread or not self.thread.is_alive():
            return "🔴 not running"
        return f"🟢 running ({self.mode})"


_daemon = WakeWordDaemon()


def start_daemon() -> str:
    return _daemon.start()


def launch_agent_console():
    """Spawn a fresh agent console (used when nothing is running)."""
    try:
        subprocess.Popen(
            [sys.executable, str(AGENT_DIR / "agent.py"), "console"],
            cwd=str(AGENT_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
        return True
    except Exception as e:
        logger.warning(f"[wake] could not launch console: {e}")
        return False
