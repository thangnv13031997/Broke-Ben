"""Turn a script into timed scenes: voice per line, scene durations, lip-sync envelopes and subtitle cues.

Subtitles: English cues are cut into short chunks (max ~6 words) timed by character count inside each line.
Vietnamese cues reuse exactly the same time slots: the line's Vietnamese text is split into the same number
of chunks, so EN and VI subtitles are always in sync with the voice.
"""
import re
import numpy as np
import tts

LEAD_IN, TAIL, MIN_SCENE = 0.25, 0.35, 2.0


def split_balanced(words, n):
    """Split words into n chunks of similar length, preferring breaks after punctuation."""
    n = max(1, min(n, len(words)))
    if n == 1:
        return [' '.join(words)]
    lens = [len(w) + 1 for w in words]
    opened, inside = 0, []                                         # no break inside a *highlight*
    for w in words:
        opened += w.count('*')
        inside.append(opened % 2 == 1)
    avg = sum(lens) / n
    INF = float('inf')
    best = [[INF] * (n + 1) for _ in range(len(words) + 1)]
    back = [[0] * (n + 1) for _ in range(len(words) + 1)]
    best[0][0] = 0.0
    for i in range(1, len(words) + 1):
        for k in range(1, n + 1):
            acc = 0
            for j in range(i - 1, k - 2, -1):
                acc += lens[j]
                if best[j][k - 1] == INF or (j > 0 and inside[j - 1]):
                    continue
                cost = best[j][k - 1] + (acc - avg) ** 2
                if i < len(words) and words[i - 1][-1:] in '.,!?;:':
                    cost -= avg * avg * 0.35                      # reward a break at punctuation
                if cost < best[i][k]:
                    best[i][k], back[i][k] = cost, j
    out, i = [], len(words)
    for k in range(n, 0, -1):
        j = back[i][k]
        out.append(' '.join(words[j:i]))
        i = j
    return out[::-1]


def chunk_words(words, n_chunks=None, max_words=6):
    if not words:
        return []
    if n_chunks is None:
        n_chunks = max(1, int(np.ceil(len(words) / max_words)))
    return split_balanced(words, n_chunks)


def cues_for_line(text, vi, t0, dur):
    """Returns (en_cues, vi_cues), each a list of (start, end, text) with identical time slots."""
    en_chunks = chunk_words(text.split())
    weights = [max(1, len(c)) for c in en_chunks]
    total = sum(weights)
    slots, t = [], t0
    for wgt in weights:
        d = dur * wgt / total
        slots.append((t, t + d))
        t += d
    vi_chunks = chunk_words(vi.split(), n_chunks=len(en_chunks)) if vi else en_chunks
    while len(vi_chunks) < len(slots):                     # very short VI line: hold it across the slots
        vi_chunks.append(vi_chunks[-1])
    en = [(a, b, c) for (a, b), c in zip(slots, en_chunks)]
    vic = [(a, b, c) for (a, b), c in zip(slots, vi_chunks)]
    return en, vic


def draw_start(sc):
    """Seconds into the scene when a sketch starts drawing (after the page has flipped or slid in)."""
    if sc['bg'] == 'notebook':
        return 0.6
    return 0.65 if sc.get('_enter') == 'slide' else 0.2


def build(script, cfg, voice, fps, test=False, progress=None, cancelled=lambda: False, log=print):
    """Synthesises (or estimates) every line and returns the timeline dict used by audio and video."""
    default_voice = script['narrator'].get('voice') or cfg.get('narrator_voice', 'am_michael')
    speed = float(script['narrator'].get('speed') or cfg.get('speed', 1.0))
    items = []
    for sc in script['scenes']:
        for ln in sc['lines']:
            ln['_segs'] = [{'text': s, 'voice': ln.get('voice') or default_voice, 'speed': speed}
                           for s in tts.segments(ln['text'])]
            items.extend(ln['_segs'])
    warnings = voice.synth(items, test=test, progress=progress, cancelled=cancelled)
    t_global = 0.0
    voice_parts, sfx_events, en_cues, vi_cues, chapters = [], [], [], [], []
    for sc in script['scenes']:
        if sc.get('chapter'):
            chapters.append((t_global, sc['chapter']))
        t = LEAD_IN
        voice_parts.append(np.zeros(int(LEAD_IN * tts.SR), np.float32))
        sc['_lines'] = []
        for li, ln in enumerate(sc['lines']):
            a = tts.line_audio(ln['_segs'], test=test)
            dur = len(a) / tts.SR
            env = tts.envelope(a, fps) if not test else None
            sc['_lines'].append({'t0': t, 't1': t + dur, 'env': env, 'speaker': ln.get('speaker', 'narrator')})
            e, v = cues_for_line(ln['text'], ln.get('vi', ''), t_global + t, dur)
            en_cues.extend(e)
            vi_cues.extend(v)
            for ev in sc['sfx']:
                if ev.get('at_line', 0) == li and 'at' not in ev:
                    sfx_events.append((t_global + t + float(ev.get('offset', 0)), ev.get('name', 'pop')))
            voice_parts.append(a)
            pause = float(ln.get('pause_after', 0.25))
            voice_parts.append(np.zeros(int(pause * tts.SR), np.float32))
            t += dur + pause
        dur = max(MIN_SCENE, t + TAIL, float(sc.get('min_secs', 0)))
        pad = dur - t
        voice_parts.append(np.zeros(int(pad * tts.SR), np.float32))
        for ev in sc['sfx']:
            if 'at' in ev:
                sfx_events.append((t_global + float(ev['at']), ev.get('name', 'pop')))
        stype = (sc.get('show') or {}).get('type')
        enter = sc.get('_enter')
        if enter == 'flip':
            sfx_events.append((t_global + 0.02, 'page'))
        elif enter == 'slide':
            sfx_events.append((t_global + 0.02, 'whoosh'))
        if stype == 'sketch':                                          # pencil sounds while the hand draws
            t_draw, end = draw_start(sc), dur * 0.75
            while t_draw < end - 0.4:
                sfx_events.append((t_global + t_draw, 'scribble'))
                t_draw += 1.6
        elif enter == 'pop' and not any(ev.get('name') for ev in sc['sfx']):
            sfx_events.append((t_global + 0.15, 'pop'))           # element pops in
        if (sc.get('show') or {}).get('type') == 'coin_drop':
            sfx_events.append((t_global + dur * 0.48, 'coin'))
        sc['start'] = t_global
        sc['duration'] = dur
        sc['frames'] = max(1, int(round(dur * fps)))
        t_global += sc['frames'] / fps                                 # keep audio and frames in lock-step
        # re-align the voice track to the frame grid
        target = int(round(t_global * tts.SR))
        cur = sum(len(x) for x in voice_parts)
        if cur < target:
            voice_parts.append(np.zeros(target - cur, np.float32))
        elif cur > target:
            voice_parts[-1] = voice_parts[-1][:max(0, len(voice_parts[-1]) - (cur - target))]
    voice_track = np.concatenate(voice_parts) if voice_parts else np.zeros(1, np.float32)
    return {'scenes': script['scenes'], 'total': t_global, 'voice': voice_track, 'sfx': sfx_events,
            'cues': {'en': en_cues, 'vi': vi_cues}, 'chapters': chapters, 'warnings': warnings}


def estimate(script, fps):
    """Timeline without any audio (for the preview slider)."""
    t_global = 0.0
    speed = float(script['narrator'].get('speed') or 1.0)
    for sc in script['scenes']:
        t = LEAD_IN
        sc['_lines'] = []
        for ln in sc['lines']:
            parts = tts.segments(ln['text'])
            dur = sum(tts.estimate_secs(s, speed) for s in parts)
            sc['_lines'].append({'t0': t, 't1': t + dur, 'env': None, 'speaker': ln.get('speaker', 'narrator')})
            t += dur + float(ln.get('pause_after', 0.25))
        sc['start'] = t_global
        sc['duration'] = max(MIN_SCENE, t + TAIL, float(sc.get('min_secs', 0)))
        sc['frames'] = max(1, int(round(sc['duration'] * fps)))
        t_global += sc['frames'] / fps
    return t_global


def fmt_srt(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def write_srt(cues, path, offset=0.0, limit=None):
    with open(path, 'w', encoding='utf-8') as f:
        n = 0
        for a, b, text in cues:
            a, b = a - offset, b - offset
            if b <= 0 or (limit is not None and a >= limit):
                continue
            n += 1
            f.write(f'{n}\n{fmt_srt(max(0, a))} --> {fmt_srt(min(b, limit) if limit else b)}\n'
                    f'{re.sub(r"[*]", "", text)}\n\n')
