"""Narration with Kokoro, the same local install the other studios use (E:\\LocalTTS\\env_en).

Money Studio never imports Kokoro itself: it writes a job file and runs tts_worker.py with
Kokoro's own Python (config "kokoro_python"), exactly like Horror Studio and Relatable Studio.
Test mode writes silent WAVs with an estimated length so the whole pipeline runs without Kokoro.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import wave
import numpy as np

SR = 24000
HERE = os.path.dirname(os.path.abspath(__file__))
NOFLAGS = 0x08000000 if sys.platform == 'win32' else 0

# Voices that ship with Kokoro-82M. The first group is already on the owner's PC.
VOICES = ['am_michael', 'af_heart', 'am_fenrir', 'af_bella', 'bm_george', 'bm_lewis', 'bf_emma', 'af_nicole',
          'af_sarah', 'am_puck', 'am_adam', 'am_eric', 'am_liam', 'am_onyx', 'af_sky', 'bf_isabella']


def read_wav(path):
    with wave.open(path, 'rb') as w:
        n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        data = resample(data, sr, SR)
    return data


def resample(x, sr_in, sr_out):
    if sr_in == sr_out or len(x) == 0:
        return x
    n = int(round(len(x) * sr_out / sr_in))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def write_wav(path, data, sr=SR, channels=1):
    d = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(d.tobytes())


def trim_silence(data, thr=0.012, keep=0.04):
    idx = np.where(np.abs(data) > thr)[0]
    if len(idx) == 0:
        return data
    k = int(keep * SR)
    return data[max(0, idx[0] - k): min(len(data), idx[-1] + k)]


def envelope(data, fps):
    """Loudness per video frame, 0..1. Drives the mascot's lip flaps."""
    hop = SR / fps
    n = int(np.ceil(len(data) / hop))
    if n == 0:
        return np.zeros(0, np.float32)
    pad = np.zeros(int(n * hop) + 1, np.float32)
    pad[:len(data)] = data
    env = np.array([np.sqrt(np.mean(pad[int(i * hop): int((i + 1) * hop)] ** 2) + 1e-12) for i in range(n)],
                   np.float32)
    ref = np.percentile(env, 92) if n > 4 else env.max()
    if ref <= 1e-5:
        return np.zeros(n, np.float32)
    env = np.clip(env / ref, 0, 1)
    env[env < 0.18] = 0
    return env


def estimate_secs(text, speed=1.0):
    return max(1, len(text.split())) / (2.6 * speed) + 0.25


SPLIT_RE = re.compile(r'\s*(?:\.\.\.|…|\s--\s|—)\s*')


def segments(text):
    """'Three grand in... thirty-three left.' -> ['Three grand in...', 'thirty-three left.'] (a beat between)."""
    parts, pos = [], 0
    for m in SPLIT_RE.finditer(text):
        seg = text[pos:m.start()].strip()
        if seg:
            parts.append(seg + ('...' if ('...' in m.group(0) or '…' in m.group(0)) else ','))
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        parts.append(tail)
    parts = [p for p in parts if re.search(r'[A-Za-z0-9]', p)]
    return parts or [text]


class Voice:
    def __init__(self, cfg, cache_dir, log=print):
        self.cfg, self.cache, self.log = cfg, cache_dir, log
        os.makedirs(cache_dir, exist_ok=True)

    def path_for(self, text, voice, speed, test):
        h = hashlib.sha1(f'{voice}|{speed:.3f}|{text}'.encode('utf-8')).hexdigest()[:16]
        return os.path.join(self.cache, ('test_' if test else '') + f'{voice}_{h}.wav')

    def check(self):
        """Human-readable status of the Kokoro connection (no audio is generated)."""
        py = self.cfg.get('kokoro_python', '')
        lines = [('OK  ' if os.path.exists(py) else 'THIẾU') + f'  Python của Kokoro: {py}']
        hf = self.cfg.get('hf_home', '')
        if hf:
            lines.append(('OK  ' if os.path.isdir(hf) else 'THIẾU') + f'  Thư mục model (HF_HOME): {hf}')
        return '\n'.join(lines), os.path.exists(py)

    def synth(self, items, test=False, progress=None, cancelled=lambda: False):
        """items: dicts with text, voice, speed. Adds 'wav' to each. Returns a list of warnings."""
        todo, seen = [], set()
        for it in items:
            it['wav'] = self.path_for(it['text'], it['voice'], it['speed'], test)
            if not os.path.exists(it['wav']) and it['wav'] not in seen:
                todo.append(it)
                seen.add(it['wav'])
        if test:
            for it in todo:
                write_wav(it['wav'], np.zeros(int(estimate_secs(it['text'], it['speed']) * SR), np.float32))
            return []
        if not todo:
            return []
        py = self.cfg.get('kokoro_python')
        if not py or not os.path.exists(py):
            raise RuntimeError('Không tìm thấy Python của Kokoro: %s\nVào tab "3. Giọng đọc" để sửa đường dẫn.' % py)
        job = {'items': [{'text': it['text'], 'voice': it['voice'], 'speed': it['speed'], 'out': it['wav']}
                         for it in todo]}
        if self.cfg.get('kokoro_device'):
            job['device'] = self.cfg['kokoro_device']
        job_path = os.path.join(self.cache, '_job.json')
        with open(job_path, 'w', encoding='utf-8') as f:
            json.dump(job, f, ensure_ascii=False)
        env = dict(os.environ)
        if self.cfg.get('hf_home'):
            env['HF_HOME'] = self.cfg['hf_home']
        env['PYTHONIOENCODING'] = 'utf-8'
        env['HF_HUB_DISABLE_TELEMETRY'] = '1'
        errors = []
        for attempt, offline in enumerate((True, False)):        # offline first; online only if a voice is missing
            env['HF_HUB_OFFLINE'] = '1' if offline else '0'
            proc = subprocess.Popen([py, os.path.join(HERE, 'tts_worker.py'), job_path], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=env, creationflags=NOFLAGS,
                                    encoding='utf-8', errors='replace')
            errors, tail = [], []
            for line in proc.stdout:
                line = line.strip()
                if cancelled():
                    proc.kill()
                    raise RuntimeError('Đã hủy')
                try:
                    msg = json.loads(line)
                except ValueError:
                    tail = (tail + [line])[-15:]
                    continue
                st = msg.get('stage')
                if st == 'line' and progress:
                    progress(msg['done'], msg['total'])
                elif st in ('line_error', 'error'):
                    errors.append(msg.get('error', ''))
                elif st == 'loading':
                    self.log('Đang nạp Kokoro...')
            proc.wait()
            missing = [it for it in todo if not os.path.exists(it['wav'])]
            if not missing:
                return errors
            if attempt == 0:
                self.log('Thử lại Kokoro có kết nối mạng (có thể thiếu file giọng mới)...')
                continue
            raise RuntimeError('Kokoro không tạo được %d câu.\n%s' % (len(missing), '\n'.join(errors[-3:] or tail[-8:])))
        return errors


def line_audio(seg_items, test=False, beat=0.3):
    """Join a line's segment WAVs with a short beat between them. Returns float32 mono at SR."""
    parts = []
    for i, it in enumerate(seg_items):
        a = read_wav(it['wav'])
        parts.append(a if test else trim_silence(a))
        if i < len(seg_items) - 1:
            parts.append(np.zeros(int((0 if test else beat) * SR), np.float32))
    return np.concatenate(parts) if parts else np.zeros(1, np.float32)
