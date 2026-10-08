from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sounds"
RATE = 44_100


def _envelope(t: float, start: float, duration: float, attack: float = 0.02) -> float:
    local = t - start
    if local < 0 or local >= duration:
        return 0.0
    fade_in = min(1.0, local / max(attack, 0.001))
    fade_out = min(1.0, (duration - local) / max(duration * 0.28, 0.001))
    return fade_in * fade_out


def _tone(t: float, start: float, duration: float, frequency: float, volume: float) -> float:
    env = _envelope(t, start, duration)
    local = max(0.0, t - start)
    return math.sin(2 * math.pi * frequency * local) * env * volume


def _metal_hit(t: float, start: float, volume: float) -> float:
    local = t - start
    if local < 0 or local > 0.42:
        return 0.0
    decay = math.exp(-local * 11)
    partials = (
        math.sin(2 * math.pi * 118 * local)
        + 0.65 * math.sin(2 * math.pi * 391 * local)
        + 0.4 * math.sin(2 * math.pi * 733 * local)
        + 0.25 * math.sin(2 * math.pi * 1_247 * local)
    )
    return partials * decay * volume


def _write(name: str, duration: float, render) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(823)
    frames: list[bytes] = []
    for index in range(int(duration * RATE)):
        t = index / RATE
        value = render(t, rng)
        value = math.tanh(value * 1.18) * 0.82
        frames.append(struct.pack("<h", int(max(-1, min(1, value)) * 32767)))
    with wave.open(str(OUT / name), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(b"".join(frames))


def opening(t: float, rng: random.Random) -> float:
    sound = _metal_hit(t, 0.03, 0.42) + _metal_hit(t, 0.16, 0.22)
    creak_env = _envelope(t, 0.20, 0.66, 0.08)
    if creak_env:
        sweep = 72 + 48 * ((t - 0.20) / 0.66)
        sound += math.sin(2 * math.pi * sweep * t + 0.9 * math.sin(t * 37)) * creak_env * 0.18
        sound += (rng.random() * 2 - 1) * creak_env * 0.08
    for offset, frequency in ((0.52, 293.66), (0.64, 369.99), (0.76, 440.0), (0.88, 587.33)):
        sound += _tone(t, offset, 0.34, frequency, 0.12)
        sound += _tone(t, offset, 0.34, frequency * 2, 0.035)
    return sound


def closing(t: float, rng: random.Random) -> float:
    whoosh = _envelope(t, 0.02, 0.52, 0.05)
    sound = (rng.random() * 2 - 1) * whoosh * (0.12 + t * 0.12)
    sound += _tone(t, 0.06, 0.46, 92 - t * 34, 0.16)
    sound += _metal_hit(t, 0.47, 0.62)
    sound += _metal_hit(t, 0.62, 0.25)
    sound += _tone(t, 0.49, 0.38, 48, 0.24)
    return sound


def main() -> None:
    _write("chest_open.wav", 1.28, opening)
    _write("chest_close.wav", 1.00, closing)
    print(f"Sonidos generados en {OUT}")


if __name__ == "__main__":
    main()
