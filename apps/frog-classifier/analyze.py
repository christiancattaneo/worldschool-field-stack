#!/usr/bin/env python3
"""Bioacoustic analysis for the frog-call classifier. stdlib only.

Reads a WAV, builds a spectrogram with a hand-written FFT, and pulls features a
field researcher cares about: how active the soundscape is, the dominant call
frequency, an estimated call count, and a heuristic frequency-band label. The
band label is a starting hypothesis, not a species ID, and the UI says so.
"""

from __future__ import annotations

import cmath
import io
import wave

TARGET_RATE = 8000      # frogs mostly call below 4 kHz; downsample for speed
FRAME = 1024            # power of two for the FFT
HOP = 512
MAX_SECONDS = 15        # cap uploads so analysis stays fast

# Heuristic frequency bands. A hypothesis to verify against a real call library.
BANDS = [
    (0, 800, "low drone, large-bodied frogs"),
    (800, 1800, "mid whistle or peep group"),
    (1800, 3000, "high chirp group, many tree frogs"),
    (3000, 99999, "very high trill, watch for insect overlap"),
]


def read_wav(data: bytes) -> tuple[list[float], int]:
    with wave.open(io.BytesIO(data), "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        n = min(n, rate * MAX_SECONDS)
        raw = w.readframes(n)
    if width != 2:
        raise ValueError("only 16-bit PCM WAV supported")
    import array
    a = array.array("h")
    a.frombytes(raw)
    samples = list(a)
    if ch == 2:  # downmix to mono
        samples = [(samples[i] + samples[i + 1]) / 2 for i in range(0, len(samples) - 1, 2)]
    peak = max((abs(s) for s in samples), default=1) or 1
    return [s / peak for s in samples], rate


def downsample(samples: list[float], rate: int, target: int = TARGET_RATE) -> tuple[list[float], int]:
    if rate <= target:
        return samples, rate
    factor = max(1, round(rate / target))
    return samples[::factor], rate // factor


def _fft(a: list[complex]) -> list[complex]:
    n = len(a)
    a = list(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        wlen = cmath.exp(-2j * cmath.pi / length)
        for i in range(0, n, length):
            w = 1 + 0j
            half = length >> 1
            for k in range(half):
                u = a[i + k]
                v = a[i + k + half] * w
                a[i + k] = u + v
                a[i + k + half] = u - v
                w *= wlen
        length <<= 1
    return a


def _hann(n: int) -> list[float]:
    import math
    return [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]


def spectrogram(samples: list[float], rate: int):
    window = _hann(FRAME)
    bins = FRAME // 2
    frames = []
    energies = []
    i = 0
    while i + FRAME <= len(samples):
        frame = [samples[i + k] * window[k] for k in range(FRAME)]
        spec = _fft([complex(x) for x in frame])
        mags = [abs(spec[b]) for b in range(bins)]
        frames.append(mags)
        energies.append(sum(m * m for m in mags))
        i += HOP
    freqs = [b * rate / FRAME for b in range(bins)]
    return frames, energies, freqs


def _resize_rows(frames, cols=64):
    if not frames:
        return []
    step = max(1, len(frames) // cols)
    return frames[::step][:cols]


def _resize_freq(mags, rows=48):
    if not mags:
        return []
    step = max(1, len(mags) // rows)
    return mags[::step][:rows]


def band_label(hz: float) -> str:
    for lo, hi, label in BANDS:
        if lo <= hz < hi:
            return label
    return "unknown"


def analyze(data: bytes) -> dict:
    samples, rate = read_wav(data)
    samples, rate = downsample(samples, rate)
    frames, energies, freqs = spectrogram(samples, rate)
    if not frames:
        return {"error": "clip too short to analyze"}

    # Dominant frequency: bin with the highest average magnitude across frames.
    bins = len(frames[0])
    col_sum = [0.0] * bins
    for f in frames:
        for b in range(bins):
            col_sum[b] += f[b]
    dom_bin = max(range(bins), key=lambda b: col_sum[b])
    dom_hz = round(freqs[dom_bin])

    # Activity and call count from the energy envelope.
    emax = max(energies) or 1.0
    env = [e / emax for e in energies]
    thresh = 0.35
    active = [v >= thresh for v in env]
    activity_pct = round(100 * sum(active) / len(active))
    calls = sum(1 for k in range(1, len(active)) if active[k] and not active[k - 1])
    if active and active[0]:
        calls += 1

    # Downsized grids for rendering (time x freq heatmap, and the envelope line).
    grid = [_resize_freq(f) for f in _resize_rows(frames)]
    gmax = max((max(r) for r in grid if r), default=1.0) or 1.0
    grid = [[round(v / gmax, 3) for v in r] for r in grid]
    env_small = env[:: max(1, len(env) // 120)][:120]

    duration = round(len(samples) / rate, 2)
    return {
        "sample_rate": rate,
        "duration_s": duration,
        "dominant_hz": dom_hz,
        "band_label": band_label(dom_hz),
        "activity_pct": activity_pct,
        "estimated_calls": calls,
        "calls_per_min": round(calls / duration * 60, 1) if duration else 0,
        "spectrogram": grid,
        "freq_max_hz": round(freqs[-1]),
        "envelope": [round(v, 3) for v in env_small],
    }
