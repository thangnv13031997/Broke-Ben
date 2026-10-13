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


DRAW_STYLES = ['pencil', 'ballpen', 'marker', 'chalk', 'tap']
DRAW_STYLE = ['pencil']                                   # set from config.json "draw_sound" before mixing


def _strokes(secs, rng, lo, hi, gap_lo, gap_hi):
    """Envelope of short uneven strokes, like a hand writing."""
    env = np.zeros(int(secs * SR), np.float32)
    starts, pos = [], 0.0
    while pos < secs:
        ln = rng.uniform(lo, hi)
        a, b = int(pos * SR), int(min(secs, pos + ln) * SR)
        if b > a:
            env[a:b] = np.sin(np.linspace(0, np.pi, b - a)) * rng.uniform(0.6, 1.0)
            starts.append(a)
        pos += ln + rng.uniform(gap_lo, gap_hi)
    return env, starts


def _fade(y, secs=0.15):
    f = min(len(y) // 2, int(secs * SR))
    y[:f] *= np.linspace(0, 1, f)
    y[-f:] *= np.linspace(1, 0, f)
    return y.astype(np.float32)


def draw_sound(style='pencil', secs=1.6):
    """Soft drawing sounds: pencil (paper shh), ballpen (light quick strokes), marker (felt-tip squeak),
    chalk (gritty taps), tap (gentle wooden taps)."""
    rng = np.random.default_rng(12)
    n = _noise(secs, 11)
    if style == 'ballpen':
        env, starts = _strokes(secs, rng, 0.06, 0.15, 0.03, 0.08)
        y = (_lowpass(n, 2) - _lowpass(n, 7)) * env * 0.22
        for a in starts:                                   # the tiny tick of the ball touching paper
            c = _lowpass(_noise(0.006, a), 2) * 0.12
            y[a:a + len(c)] += c[:len(y) - a]
        return _fade(y)
    if style == 'marker':
        env, _ = _strokes(secs, rng, 0.18, 0.4, 0.06, 0.14)
        t = np.arange(len(n)) / SR
        f = 1050 + 250 * np.sin(2 * np.pi * 3.1 * t) + 120 * np.sin(2 * np.pi * 7.7 * t)
        squeak = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.035
        y = ((_lowpass(n, 6) - _lowpass(n, 40)) * 0.3 + squeak) * env
        return _fade(y)
    if style == 'chalk':
        env, starts = _strokes(secs, rng, 0.1, 0.25, 0.05, 0.12)
        grit = (_lowpass(n, 3) - _lowpass(n, 12)) * (0.6 + 0.4 * (np.abs(_noise(secs, 21)) > 1.2))
        y = grit * env * 0.3
        for a in starts:
            c = _lowpass(_noise(0.02, a + 1), 6) * _env(int(0.02 * SR), 0.001, 0.006) * 0.35
            y[a:a + len(c)] += c[:len(y) - a]
        return _fade(y)
    if style == 'tap':
        y = np.zeros(int(secs * SR), np.float32)
        pos = 0.05
        while pos < secs - 0.1:
            a = int(pos * SR)
            tick = _tone(rng.uniform(900, 1300), 0.05, 0.012, (1, 0.3)) * rng.uniform(0.3, 0.45)
            y[a:a + len(tick)] += tick[:len(y) - a]
            pos += rng.uniform(0.14, 0.26)
        return _fade(y, 0.05)
    env, _ = _strokes(secs, rng, 0.12, 0.28, 0.04, 0.12)  # pencil: a soft paper "shh"
    y = (_lowpass(n, 4) - _lowpass(n, 18)) * env * 0.25
    return _fade(y)


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
    if name == 'scribble':                               # the drawing sound, ~1.6 s, kept quiet
        return draw_sound(DRAW_STYLE[0])
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
    draw_vol = float(cfg.get('draw_volume', 0.5))           # the pencil has its own volume (0 = silent)
    DRAW_STYLE[0] = cfg.get('draw_sound', 'pencil') if cfg.get('draw_sound') in DRAW_STYLES else 'pencil'
    for t, name in events:
        g = vol * (draw_vol if name == 'scribble' else 1.0)
        if g <= 0:
            continue
        s = sfx(name) * g
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
