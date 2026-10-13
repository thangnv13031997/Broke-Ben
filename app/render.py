"""Export pipeline: voice (Kokoro) -> timeline -> mix -> frames (parallel) -> MP4 + Short + thumbnails + texts.

Command line (handy for testing without the window):
    python app/render.py scripts/ep00_trailer.json --subs vi --test
"""
import json
import os
import pickle
import re
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np            # noqa: E402
import audio                  # noqa: E402
import script_io              # noqa: E402
import timeline               # noqa: E402
import tts                    # noqa: E402
import youtube                # noqa: E402

NOFLAGS = 0x08000000 if sys.platform == 'win32' else 0
OUTPUT = os.path.join(ROOT, 'output')
_ENC = {}


def ffmpeg_exe(cfg):
    p = cfg.get('ffmpeg')
    if p and os.path.exists(p):
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'


def pick_encoder(ff, want):
    if want == 'libx264':
        return 'libx264'
    if 'enc' not in _ENC:
        enc = 'libx264'
        try:
            r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                                'color=c=black:s=320x240:d=0.2', '-c:v', 'h264_nvenc', '-f', 'null', '-'],
                               capture_output=True, timeout=30, creationflags=NOFLAGS)
            if r.returncode == 0:
                enc = 'h264_nvenc'
        except Exception:
            pass
        _ENC['enc'] = enc
    return _ENC['enc']


def slugify(s):
    return re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-')[:60] or 'video'


def fmt_ts(sec):
    return youtube.fmt_ts(sec)


class Job:
    """One export. report(kind, fraction, text) is called from the worker thread."""

    def __init__(self, cfg, script_path, subs='en', test_voice=False, preview_secs=None, shorts=True,
                 report=None, log=print):
        self.cfg, self.script_path = cfg, script_path
        self.subs = subs if subs in ('en', 'vi', 'none') else 'en'
        self.test_voice, self.preview_secs, self.make_shorts = test_voice, preview_secs, shorts
        self._report = report or (lambda k, f, t: None)
        self.log = log
        self.cancel = False
        self.fps = int(cfg.get('fps', 30))
        self.W, self.H = 1920, 1080

    def report(self, kind, frac, text):
        self._report(kind, frac, text)

    def run(self):
        t0 = time.time()
        script = script_io.load(self.script_path)
        errs = [m for lvl, m in script_io.check(script) if lvl == 'LỖI']
        if errs:
            raise RuntimeError('Kịch bản có lỗi:\n- ' + '\n- '.join(errs[:8]))
        stamp = time.strftime('%Y%m%d_%H%M')
        name = f'{stamp}_{slugify(script["title"])}' + ('_PREVIEW' if self.preview_secs else '') + \
            ('_TEST' if self.test_voice else '')
        out_dir = os.path.join(OUTPUT, name)
        os.makedirs(out_dir, exist_ok=True)
        ff = ffmpeg_exe(self.cfg)
        enc = pick_encoder(ff, self.cfg.get('encoder', 'auto'))

        self.report('voice', 0, 'Tạo giọng đọc bằng Kokoro...')
        voice = tts.Voice(self.cfg, os.path.join(OUTPUT, '_tts_cache'), log=self.log)
        tl = timeline.build(script, self.cfg, voice, self.fps, test=self.test_voice,
                            progress=lambda d, n: self.report('voice', d / max(1, n), f'Giọng đọc {d}/{n} câu'),
                            cancelled=lambda: self.cancel, log=self.log)
        for w in tl['warnings'][:3]:
            self.log('Kokoro: ' + w)
        total = tl['total']
        scenes = script['scenes']
        ids = list(range(len(scenes)))
        if self.preview_secs:
            ids, acc = [], 0.0
            for i, sc in enumerate(scenes):
                ids.append(i)
                acc += sc['duration']
                if acc >= self.preview_secs:
                    break
            total = sum(scenes[i]['frames'] for i in ids) / self.fps
        self.log(f'Thời lượng: {fmt_ts(total)} ({len(ids)} cảnh) | phụ đề: {script_io.SUB_LANGS[self.subs]} | '
                 f'bộ mã hóa: {enc}')

        self.report('audio', 0, 'Trộn giọng, nhạc nền, hiệu ứng...')
        mixed = audio.mix(tl['voice'], tl['sfx'], tl['total'], script.get('music', 'light'), ff, self.cfg)
        wav = os.path.join(out_dir, '_mix.wav')
        tts.write_wav(wav, mixed[:int(total * tts.SR)])

        t_frames = time.time()
        frames = sum(scenes[i]['frames'] for i in ids)
        segs = self.render_video(ff, enc, out_dir, script, tl, ids, frames, t_frames, vertical=False)
        mp4 = os.path.join(out_dir, 'video.mp4')
        self.mux(ff, segs, wav, mp4)
        for s in segs:
            _rm(s)

        if self.make_shorts and not self.preview_secs:
            sids = _shorts_ids(script, self.fps)
            if sids:
                self.report('frames', 0, 'Dựng bản Shorts dọc...')
                s_frames = sum(scenes[i]['frames'] for i in sids)
                s0 = scenes[sids[0]]['start']
                s_total = s_frames / self.fps
                segs = self.render_video(ff, enc, out_dir, script, tl, sids, s_frames, time.time(), vertical=True,
                                         prefix='_short', shorts_info={'start': s0, 'total': s_total})
                self.mux(ff, segs, wav, os.path.join(out_dir, 'shorts.mp4'), start=s0, dur=s_total)
                for s in segs:
                    _rm(s)

        self.report('extras', 0.95, 'Phụ đề, thumbnail, nội dung YouTube...')
        limit = total if self.preview_secs else None
        timeline.write_srt(tl['cues']['en'], os.path.join(out_dir, 'subtitles_en.srt'), limit=limit)
        timeline.write_srt(tl['cues']['vi'], os.path.join(out_dir, 'subtitles_vi.srt'), limit=limit)
        try:
            import thumbnail
            for i, im in enumerate(thumbnail.render_all(script)):
                im.convert('RGB').save(os.path.join(out_dir, f'thumbnail_{"ABC"[i]}.jpg'), quality=92)
        except Exception:
            self.log('Thumbnail lỗi (video vẫn xuất bình thường):\n' + traceback.format_exc()[-600:])
        youtube.write(script, tl['chapters'], total, os.path.join(out_dir, 'youtube.txt'))
        _rm(wav)
        took = time.time() - t0
        with open(os.path.join(out_dir, 'render_report.txt'), 'w', encoding='utf-8') as f:
            f.write(f'Thư mục: {out_dir}\nThời lượng: {fmt_ts(total)} ({len(ids)} cảnh)\n'
                    f'Phụ đề trên video: {script_io.SUB_LANGS[self.subs]}\nBộ mã hóa: {enc}\n'
                    f'Thời gian xuất: {fmt_ts(took)}\n\nKiểm tra kịch bản:\n')
            for lvl, m in script_io.check(script):
                f.write(f'- [{lvl}] {m}\n')
        self.report('done', 1, f'Xong trong {fmt_ts(took)}')
        return out_dir

    # ------------------------------------------------------------ video
    def render_video(self, ff, enc, out_dir, script, tl, ids, total_frames, t_frames, vertical, prefix='_seg',
                     shorts_info=None):
        import multiprocessing as mp
        workers = self.cfg.get('workers', 'auto')
        if workers in ('auto', None, 0):
            workers = max(1, min(6, (os.cpu_count() or 2) - 1))
        workers = max(1, min(int(workers), len(ids)))
        groups, cur, acc = [], [], 0
        per = total_frames / workers
        for i in ids:
            cur.append(i)
            acc += script['scenes'][i]['frames']
            if acc >= per * (len(groups) + 1) and len(groups) < workers - 1:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        light = {'scenes': [{k: v for k, v in sc.items() if not k.startswith('_') or k == '_lines'}
                            for sc in script['scenes']],
                 'cues': tl['cues'], 'shorts': script.get('shorts') or {}}
        for sc in light['scenes']:
            sc['_lines'] = [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in ln.items()}
                            for ln in sc.get('_lines', [])]
        pk = os.path.join(out_dir, prefix + '_job.pkl')
        with open(pk, 'wb') as f:
            pickle.dump(light, f)
        segs = [os.path.join(out_dir, f'{prefix}{i:02d}.mp4') for i in range(len(groups))]
        base = dict(W=self.W, H=self.H, fps=self.fps, enc=enc, ff=ff, subs=self.subs, vertical=vertical,
                    quality=int(self.cfg.get('quality', 2)), x264_preset=self.cfg.get('x264_preset', 'veryfast'),
                    shorts=shorts_info or {})
        done = 0
        if len(groups) == 1:
            q = _LocalQ(self, total_frames, t_frames)
            _segment_worker(pk, groups[0], segs[0], base, q, _Flag(self))
            if q.error:
                raise RuntimeError('Lỗi dựng hình:\n' + q.error[-800:])
        else:
            ctx = mp.get_context('spawn')
            q, stop = ctx.Queue(), ctx.Event()
            procs = []
            self.log(f'Dựng hình song song: {len(groups)} luồng')
            for g, sp in zip(groups, segs):
                p = ctx.Process(target=_segment_worker, args=(pk, g, sp, base, q, stop), daemon=True)
                p.start()
                procs.append(p)
            finished, errors = 0, []
            while finished < len(procs):
                if self.cancel:
                    stop.set()
                    for p in procs:
                        p.join(5)
                        if p.is_alive():
                            p.terminate()
                    raise RuntimeError('Đã hủy')
                try:
                    msg = q.get(timeout=0.5)
                except Exception:
                    if all(not p.is_alive() for p in procs) and q.empty():
                        break
                    continue
                if msg[0] == 'p':
                    done += msg[1]
                    el = time.time() - t_frames
                    eta = el / max(1, done) * (total_frames - done)
                    self.report('frames', done / total_frames,
                                f'Dựng hình {done}/{total_frames} khung, còn khoảng {fmt_ts(eta)}')
                elif msg[0] == 'done':
                    finished += 1
                    if msg[1]:
                        errors.append(msg[1])
            for p in procs:
                p.join(10)
            if errors:
                if enc == 'h264_nvenc':
                    _ENC['enc'] = 'libx264'
                    self.log('NVENC lỗi, lần sau sẽ dùng libx264.')
                raise RuntimeError('Lỗi dựng hình:\n' + errors[0][-800:])
        _rm(pk)
        missing = [s for s in segs if not os.path.exists(s)]
        if missing:
            raise RuntimeError('Thiếu đoạn video: ' + ', '.join(os.path.basename(m) for m in missing))
        return segs

    def mux(self, ff, segs, wav, mp4, start=None, dur=None):
        lst = mp4 + '_segments.txt'
        with open(lst, 'w', encoding='utf-8') as f:
            for s in segs:
                f.write("file '" + s.replace('\\', '/').replace("'", "'\\''") + "'\n")
        cmd = [ff, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst]
        if start is not None:
            cmd += ['-ss', f'{start:.3f}', '-t', f'{dur:.3f}']
        cmd += ['-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar',
                '48000', '-ac', '2', '-shortest', '-movflags', '+faststart', mp4]
        r = subprocess.run(cmd, capture_output=True, creationflags=NOFLAGS)
        _rm(lst)
        if r.returncode != 0:
            raise RuntimeError('ffmpeg ghép video lỗi:\n' + r.stderr.decode('utf-8', 'replace')[-800:])


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


def _shorts_ids(script, fps):
    """Scenes for the vertical Short: script.shorts.scenes [from, to] (1-based) or the opening scenes up to 55 s."""
    rng = (script.get('shorts') or {}).get('scenes')
    scenes = script['scenes']
    if rng and len(rng) == 2:
        ids = list(range(max(0, int(rng[0]) - 1), min(len(scenes), int(rng[1]))))
    else:
        ids = []
    out, acc = [], 0.0
    for i in ids or range(len(scenes)):
        if acc + scenes[i]['duration'] > 58:
            break
        out.append(i)
        acc += scenes[i]['duration']
    return out


class _LocalQ:
    """Progress sink when rendering in this process (one worker)."""

    def __init__(self, job, total, t0):
        self.job, self.total, self.t0, self.done, self.error = job, total, t0, 0, None

    def put(self, msg):
        if msg[0] == 'p':
            self.done += msg[1]
            eta = (time.time() - self.t0) / max(1, self.done) * (self.total - self.done)
            self.job.report('frames', self.done / max(1, self.total),
                            f'Dựng hình {self.done}/{self.total} khung, còn khoảng {fmt_ts(eta)}')
        elif msg[0] == 'done' and msg[1]:
            self.error = msg[1]


class _Flag:
    def __init__(self, job):
        self.job = job

    def is_set(self):
        return self.job.cancel


def _segment_worker(pk, scene_ids, seg_path, base, q, stop):
    proc = None
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import scene
        with open(pk, 'rb') as f:
            job = pickle.load(f)
        fps = base['fps']
        OW, OH = (1080, 1920) if base['vertical'] else (base['W'], base['H'])
        cmd = [base['ff'], '-y', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{OW}x{OH}', '-r', str(fps), '-i', '-']
        if base['enc'] == 'h264_nvenc':
            cmd += ['-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr', '-cq', '23', '-b:v', '0',
                    '-maxrate', '20M', '-bufsize', '40M', '-g', str(fps * 2)]
        else:
            cmd += ['-c:v', 'libx264', '-preset', base['x264_preset'], '-crf', '21', '-g', str(fps * 2)]
        cmd += ['-pix_fmt', 'yuv420p', '-an', seg_path]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NOFLAGS)
        R = scene.Renderer(base['W'], base['H'], fps, base['subs'], job['cues'], base['quality'])
        sh = base.get('shorts') or {}
        hook = (job.get('shorts') or {}).get('hook_text', '')
        end = (job.get('shorts') or {}).get('end_text', 'Full video on the channel')
        n = 0
        for si in scene_ids:
            sc = job['scenes'][si]
            for i in range(sc['frames']):
                if stop.is_set():
                    proc.kill()
                    q.put(('done', 'Đã hủy'))
                    return
                t = i / fps
                if base['vertical']:
                    gt = sc['start'] + t - sh.get('start', 0)
                    img = scene.vertical(R, sc, t, hook, gt, sh.get('total', 60), end)
                else:
                    img = R.frame(sc, t)
                proc.stdin.write(img.tobytes())
                n += 1
                if n % 10 == 0:
                    q.put(('p', 10))
        q.put(('p', n % 10))
        proc.stdin.close()
        err = proc.stderr.read().decode('utf-8', 'replace')
        proc.wait()
        q.put(('done', None if proc.returncode == 0 else 'ffmpeg: ' + err))
    except Exception:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        q.put(('done', traceback.format_exc()))


_STILL = {}


def still(cfg, script_path, scene_index, at=0.6, width=960, subs='en'):
    """Preview image of one scene (estimated timing, no audio).
    Returns (PIL image, scene count, total secs, the timed scene dict)."""
    import scene
    script = script_io.load(script_path)
    fps = int(cfg.get('fps', 30))
    total = timeline.estimate(script, fps)
    cues = {'en': [], 'vi': []}
    for sc in script['scenes']:
        for ln, tm in zip(sc['lines'], sc['_lines']):
            e, v = timeline.cues_for_line(ln['text'], ln.get('vi', ''), sc['start'] + tm['t0'], tm['t1'] - tm['t0'])
            cues['en'].extend(e)
            cues['vi'].extend(v)
    if not script['scenes']:
        return None, 0, 0, None
    scene_index = max(0, min(scene_index, len(script['scenes']) - 1))
    sc = script['scenes'][scene_index]
    key = (width, fps)
    R = _STILL.get(key)
    if R is None:
        R = _STILL[key] = scene.Renderer(width, int(width * 9 / 16), fps, subs, cues, quality=1)
    R.subs, R.cues = subs, cues                       # sprites and backgrounds stay cached between calls
    R._starts = {lang: [c[0] for c in cues.get(lang, [])] for lang in ('en', 'vi')}
    R._el.clear()
    t = sc['_lines'][0]['t0'] + 0.5 if (sc['_lines'] and at is None) else sc['duration'] * at
    return R.frame(sc, t), len(script['scenes']), total, sc


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Money Studio export (command line)')
    ap.add_argument('script')
    ap.add_argument('--subs', choices=['en', 'vi', 'none'], default='en')
    ap.add_argument('--test', action='store_true', help='silent voice with estimated timing (no Kokoro)')
    ap.add_argument('--preview', type=float, default=None, help='only the first N seconds')
    ap.add_argument('--no-shorts', action='store_true')
    a = ap.parse_args()
    with open(os.path.join(ROOT, 'config.json'), 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    job = Job(cfg, a.script, subs=a.subs, test_voice=a.test, preview_secs=a.preview, shorts=not a.no_shorts,
              report=lambda k, fr, t: print(f'[{k} {fr:4.0%}] {t}', flush=True))
    print(job.run())


if __name__ == '__main__':
    main()
