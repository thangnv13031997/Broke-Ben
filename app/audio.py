"""Music bed, sound effects and the final mix (numpy only).

Built-in sounds are synthesised, so there is no copyright risk. To use your own music, drop a licensed
file into library/music/<style>/ (light, thoughtful); your file always wins over the built-in bed.
Your own effects go in library/sfx/<name>.wav (pop, coin, ding, whoosh, tick, thud, cash, page, scribble).
"""
import glob
import os
import subprocess
import sys
import numpy as np
from tts import SR, read_wav

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'library')
NOFLAGS = 0x08000000 if sys.platform == 'win32' else 0


# ---------------------------------------------------------------- synthesis helpers
def _t(secs):
    return np.arange(int(secs * SR)) / SR


def _env(n, a=0.005, d=0.25):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))


def _tone(freq, secs, d=0.3, harm=(1.0, 0.3, 0.1)):
    t = _t(secs)
    x = sum(a * np.sin(2 * np.pi * freq * (k + 1) * t) for k, a in enumerate(harm))
    return (x * _env(len(t), 0.004, d)).astype(np.float32)


def _noise(secs, seed=0):
    return np.random.default_rng(seed).normal(0, 1, int(secs * SR)).astype(np.float32)


def _lowpass(x, k):
    k = max(1, int(k))
    return np.convolve(x, np.ones(k) / k, mode='same').astype(np.float32)


def sfx(name):
    own = os.path.join(LIB, 'sfx', name + '.wav')
    if os.path.exists(own):
        try:
            return read_wav(own)
        except Exception:
            pass
    if name == 'pop':
        t = _t(0.12)
        f = 900 - 500 * t / 0.12
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 0.04) * 0.6).astype(np.float32)
    if name == 'coin':
        a = _tone(1975.5, 0.5, 0.18, (1, 0.2))
        b = _tone(2637.0, 0.6, 0.25, (1, 0.2))
        out = np.zeros(int(0.7 * SR), np.float32)
        out[:len(a)] += a * 0.45
        o = int(0.07 * SR)
        out[o:o + len(b)] += b * 0.5
        return out
    if name == 'ding':
        return _tone(1318.5, 1.2, 0.45, (1, 0.5, 0.25, 0.1)) * 0.4
    if name == 'cash':
        out = np.zeros(int(0.9 * SR), np.float32)
        click = _lowpass(_noise(0.03, 3), 2) * 0.5
        out[:len(click)] += click
        bell = _tone(2093.0, 0.8, 0.35, (1, 0.4)) * 0.45
        o = int(0.08 * SR)
        out[o:o + len(bell)] += bell
        return out
    if name == 'whoosh':
        n = _noise(0.45, 5)
        t = np.linspace(0, 1, len(n))
        k = (3 + 25 * (1 - np.sin(np.pi * t))).astype(int)
        y = np.array([n[max(0, i - kk):i + 1].mean() for i, kk in enumerate(k)], np.float32)
        return y * np.sin(np.pi * t) * 1.4
    if name == 'tick':
        return _tone(3000, 0.03, 0.008, (1,)) * 0.35
    if name == 'page':                                   # paper page turning
        n = _noise(0.55, 9)
        t = np.linspace(0, 1, len(n))
        y = (n - _lowpass(n, 6)) * np.sin(np.pi * t) ** 1.5 * 0.5
        return y.astype(np.float32)
    if name == 'scribble':                               # marker on paper, ~1.6 s
        n = _noise(1.6, 11)
        t = np.arange(len(n)) / SR
        strokes = 0.5 + 0.5 * np.sin(2 * np.pi * 5.3 * t) * np.sin(2 * np.pi * 1.7 * t + 1)
        y = (n - _lowpass(n, 3)) * np.clip(strokes, 0, 1) * 0.22
        f = int(0.08 * SR)
        y[:f] *= np.linspace(0, 1, f)
        y[-f:] *= np.linspace(1, 0, f)
        return y.astype(np.float32)
    if name == 'thud':
        t = _t(0.3)
        f = 120 - 70 * t / 0.3
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 0.09) * 0.9).astype(np.float32)
    return np.zeros(1, np.float32)


# ---------------------------------------------------------------- music bed
NOTE = {'C': 261.63, 'D': 293.66, 'E': 329.63, 'F': 349.23, 'G': 392.0, 'A': 440.0, 'B': 493.88}
PROGRESSIONS = {
    'light': (104, [('C', 'E', 'G'), ('A', 'C', 'E'), ('F', 'A', 'C'), ('G', 'B', 'D')]),
    'thoughtful': (84, [('A', 'C', 'E'), ('F', 'A', 'C'), ('C', 'E', 'G'), ('G', 'B', 'D')]),
}


def _bed(style, secs):
    bpm, chords = PROGRESSIONS.get(style, PROGRESSIONS['light'])
    beat = 60.0 / bpm
    bar = beat * 4
    loop = np.zeros(int(bar * len(chords) * SR) + SR, np.float32)
    for ci, ch in enumerate(chords):
        o = int(ci * bar * SR)
        for k, nme in enumerate(ch):                         # soft pad
            f = NOTE[nme] / 2
            t = _t(bar)
            pad = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * 0.06
            pad *= np.minimum(1, t / 0.3) * np.minimum(1, (bar - t) / 0.3)
            loop[o:o + len(pad)] += pad.astype(np.float32)
        for b in range(8):                                   # light plucks on eighth notes
            nme = ch[(b * 2 + (b // 4)) % 3]
            p = _tone(NOTE[nme] * (2 if b % 4 == 3 else 1), beat, 0.18, (1, 0.25)) * (0.12 if b % 2 == 0 else 0.07)
            s = o + int(b * beat / 2 * SR)
            loop[s:s + len(p)] += p
        kick = _tone(55, 0.25, 0.08, (1,)) * 0.18
        for b in (0, 2):
            s = o + int(b * beat * SR)
            loop[s:s + len(kick)] += kick
    loop = loop[:int(bar * len(chords) * SR)]
    reps = int(np.ceil(secs * SR / len(loop))) + 1
    return np.tile(loop, reps)[:int(secs * SR)]


def _own_music(style, ff):
    files = sorted(glob.glob(os.path.join(LIB, 'music', style, '*.*')))
    files = [f for f in files if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))]
    if not files:
        return None
    try:
        r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-i', files[0], '-f', 's16le', '-ac', '1',
                            '-ar', str(SR), '-'], capture_output=True, creationflags=NOFLAGS, timeout=300)
        if r.returncode == 0 and r.stdout:
            return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0
    except Exception:
        pass
    return None


def music(style, secs, ff):
    if style == 'none':
        return np.zeros(int(secs * SR), np.float32)
    own = _own_music(style, ff)
    if own is not None and len(own) > SR:
        reps = int(np.ceil(secs * SR / len(own))) + 1
        x = np.tile(own, reps)[:int(secs * SR)]
        return x / (np.max(np.abs(x)) + 1e-6) * 0.5
    return _bed(style, secs)


# ---------------------------------------------------------------- mix
def mix(voice, events, total_secs, style, ff, cfg):
    """voice: float32 narration track; events: [(time, sfx_name)]. Returns stereo-ready mono float32."""
    n = int(total_secs * SR)
    out = np.zeros(n, np.float32)
    v = voice[:n]
    out[:len(v)] += v * float(cfg.get('voice_volume', 1.0))
    bed = music(style, total_secs, ff) * float(cfg.get('music_volume', 0.35))
    # duck the music under the voice (smoothed loudness)
    k = int(0.25 * SR)
    loud = np.abs(np.pad(voice, (0, max(0, n - len(voice))))[:n])
    loud = np.convolve(loud, np.ones(k) / k, mode='same')
    duck = 1 - 0.6 * np.clip(loud / 0.05, 0, 1)
    out += bed[:n] * duck.astype(np.float32)
    vol = float(cfg.get('sfx_volume', 0.8))
    for t, name in events:
        s = sfx(name) * vol
        i = int(t * SR)
        if 0 <= i < n:
            m = min(len(s), n - i)
            out[i:i + m] += s[:m]
    peak = float(np.max(np.abs(out))) if n else 0
    if peak > 0.97:
        out *= 0.97 / peak
    # short fade in/out
    f = min(n // 2, int(0.4 * SR))
    if f > 0:
        out[:f] *= np.linspace(0, 1, f)
        out[-f:] *= np.linspace(1, 0, f)
    return out
