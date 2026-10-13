"""Frame composer: background + money element + mascots + chapter tag + subtitles.

Animation is cut-out style: mascots are cached sprites; life comes from breathing, blinking, lip flaps
driven by the voice loudness, hops, pop-in/slide-in elements, a pencil reveal on notebook scenes,
and a coin dropping into Piggy Ben.
"""
import bisect
import math
import random
from PIL import Image, ImageDraw
from engine.flatkit import Pen, font
from engine import charkit
import elements as EL

INK, MUTED, CREAM = (29, 33, 45), (112, 108, 100), (246, 241, 230)
GOLD, GREEN = (255, 196, 61), (46, 139, 87)
FLOOR_Y = 905


def _ease_out_back(t):
    return EL.ease_out_back(t)


class Renderer:
    def __init__(self, W=1920, H=1080, fps=30, subs='en', cues=None, quality=2):
        self.W, self.H, self.fps = W, H, fps
        self.k = W / 1920.0
        self.subs = subs
        self.cues = cues or {'en': [], 'vi': []}
        self._starts = {lang: [c[0] for c in self.cues.get(lang, [])] for lang in ('en', 'vi')}
        self.S = 2 if quality >= 2 else 1
        self._bg, self._spr, self._el, self._cap = {}, {}, {}, {}

    # ------------------------------------------------------------ cached pieces
    def background(self, name):
        if name in self._bg:
            return self._bg[name]
        W, H = 1920, 1080
        p = Pen(W, H, 1)
        if name == 'room':
            p.vgrad((0, 0, W, H), '#45566E', '#2C3646')
            p.rect((90, 70, 450, 330), '#1C2433', '#5A6A82', 10, r=8)
            rnd = random.Random(3)
            for i in range(6):
                bx = 104 + i * 56
                bh = rnd.randint(70, 200)
                p.rect((bx, 330 - bh, bx + 48, 320), '#2B3548')
                for kk in range(bh // 34):
                    if rnd.random() < 0.55:
                        p.rect((bx + 12, 330 - bh + 14 + kk * 34, bx + 24, 330 - bh + 26 + kk * 34), '#F3C969')
            p.line([(270, 70), (270, 330)], 10, '#5A6A82', caps=False)
            p.rect((0, FLOOR_Y - 8, W, H), '#6B4F3A')
            p.rect((0, FLOOR_Y - 14, W, FLOOR_Y), '#86654B')
        elif name == 'desk':
            p.vgrad((0, 0, W, H), '#F2E6D2', '#E4D2B4')
            p.rect((60, 90, 290, 330), '#FFFFFF', '#C9B89A', 6, r=10)
            for i in range(4):
                p.rect((88, 124 + i * 50, 262 - (i % 3) * 36, 142 + i * 50), (226, 214, 190))
            p.rect((0, FLOOR_Y - 8, W, H), '#9A6B45')
            p.rect((0, FLOOR_Y - 14, W, FLOOR_Y), '#B07D53')
        elif name == 'city':
            p.vgrad((0, 0, W, H), '#9FD3F0', '#E9F5FB')
            rnd = random.Random(7)
            x = 0
            while x < W:
                bw, bh = rnd.randint(90, 180), rnd.randint(220, 560)
                col = rnd.choice(['#7A8FA6', '#8FA3B8', '#6E8399'])
                p.rect((x, FLOOR_Y - bh, x + bw - 8, FLOOR_Y), col)
                for wy in range(FLOOR_Y - bh + 24, FLOOR_Y - 30, 44):
                    for wx in range(x + 14, x + bw - 30, 34):
                        p.rect((wx, wy, wx + 16, wy + 22), '#DCEBF5')
                x += bw
            p.rect((0, FLOOR_Y, W, H), '#5C636E')
            p.rect((0, FLOOR_Y, W, FLOOR_Y + 8), '#C9CED6')
        elif name == 'notebook':
            p.rect((0, 0, W, H), '#FBF8EF')
            for y in range(150, H, 56):
                p.line([(0, y), (W, y)], 2, (170, 200, 230), caps=False)
            p.line([(170, 0), (170, H)], 3, (232, 120, 120), caps=False)
            for y in (220, 540, 860):
                p.circle(70, y, 22, (225, 220, 205))
        elif name == 'plain':
            p.rect((0, 0, W, H), CREAM)
        else:                                                             # grid (default)
            p.vgrad((0, 0, W, H), '#FBF7EE', '#ECE3CF')
            grid = p.layer()                   # translucent lines must be blended, not written
            for x in range(0, W, 64):
                grid.line([(x, 0), (x, H)], 1.5, (0, 0, 0, 22), caps=False)
            for y in range(0, H, 64):
                grid.line([(0, y), (W, y)], 1.5, (0, 0, 0, 22), caps=False)
            p.paste(grid)
            p.rect((0, FLOOR_Y, W, H), (226, 214, 190))
            p.rect((0, FLOOR_Y - 4, W, FLOOR_Y + 2), (205, 190, 160))
        img = p.img.convert('RGB')
        if self.k != 1:
            img = img.resize((self.W, self.H), Image.BICUBIC)
        self._bg[name] = img
        return img

    def sprite(self, who, pose, mood, blink, talk, height):
        key = (who, pose, mood, blink, talk, int(height))
        if key not in self._spr:
            if who == 'piggy':
                pm = 'shock' if mood in ('shock', 'sad', 'worried', 'angry') else 'smile'
                im = charkit.piggy(mood=pm, blink=blink, talk=talk)
            else:
                im = charkit.ben(pose=pose, mood=mood, blink=blink, talk=talk)   # unknown values fall back inside
            bb = im.getbbox()
            im = im.crop(bb)
            k = height / im.height
            im = im.resize((max(1, int(im.width * k)), max(1, int(height))), Image.LANCZOS)
            self._spr[key] = (im, bb, k)
        return self._spr[key]

    def element(self, sc, w, h, p):
        """w, h in 1920-wide design units; drawn at that size (fonts are tuned for it), then scaled."""
        step = round(p * 90)
        key = (sc['index'], step, int(w), int(h))
        if key not in self._el:
            if len(self._el) > 400:
                self._el.clear()
            im = EL.render(sc['show'], w, h, step / 90.0, S=self.S)
            if im is not None and self.k != 1:
                im = im.resize((max(1, int(w * self.k)), max(1, int(h * self.k))), Image.LANCZOS)
            self._el[key] = im
        return self._el[key]

    def caption_img(self, text):
        if text in self._cap:
            return self._cap[text]
        size = int(50 * self.k)
        f = font('semi', size)
        words = text.split()
        maxw = self.W * 0.8
        lines, cur = [], ''
        for wd in words:
            tryl = (cur + ' ' + wd).strip()
            if f.getlength(tryl.replace('*', '')) > maxw and cur:
                lines.append(cur)
                cur = wd
            else:
                cur = tryl
        if cur:
            lines.append(cur)
        lh = int(size * 1.25)
        tw = max(f.getlength(ln.replace('*', '')) for ln in lines)
        pad = int(30 * self.k)
        img = Image.new('RGBA', (int(tw + pad * 2), lh * len(lines) + pad), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), int(lh * 0.5), fill=(14, 16, 22, 215))
        for i, ln in enumerate(lines):
            x = (img.width - f.getlength(ln.replace('*', ''))) / 2
            y = pad / 2 + i * lh + lh / 2
            hi = False
            for part in ln.split('*'):
                if part:
                    d.text((x, y), part, font=f, fill=GOLD if hi else (250, 250, 245), anchor='lm')
                    x += f.getlength(part)
                hi = not hi
        self._cap[text] = img
        if len(self._cap) > 300:
            self._cap.pop(next(iter(self._cap)))
        return img

    def cue_at(self, gt, lang=None):
        lang = lang or self.subs
        if lang not in ('en', 'vi'):
            return None
        cues = self.cues.get(lang) or []
        i = bisect.bisect_right(self._starts[lang], gt) - 1
        if 0 <= i < len(cues) and cues[i][0] <= gt < cues[i][1]:
            return cues[i][2]
        return None

    # ------------------------------------------------------------ frame
    def layout(self, sc):
        show = sc.get('show') or {}
        side = show and show.get('type') not in (None, 'coin_drop')
        chars = sc['chars']
        xs = []
        for i, c in enumerate(chars):
            if 'x' in c:
                xs.append(float(c['x']))
            elif side:
                xs.append([0.2, 0.08, 0.32][i % 3] if len(chars) > 1 else 0.2)
            else:
                n = len(chars)
                xs.append(0.5 if n == 1 else 0.3 + 0.4 * i / (n - 1))
        box = (700, 110, 1860, 890) if (side and chars) else (380, 110, 1540, 890)
        return side, xs, box

    def progress(self, sc, t):
        """Animation progress of the scene's element. Counting elements (money card / phone with a change)
        run while the line that announces the change is spoken; everything else builds over the scene."""
        show = sc.get('show') or {}
        lines = sc.get('_lines') or []
        counting = show.get('type') in ('money_card', 'phone') and ('to' in show or 'from' in show)
        if counting and lines:
            a = lines[1]['t0'] if len(lines) > 1 else lines[0]['t0'] + 0.3
            b = lines[-1]['t1']
            return EL.clamp((t - a) / max(0.6, b - a))
        return EL.clamp(t / max(1.2, sc['duration'] * 0.9))

    def talking(self, sc, t, ci, c):
        for ln in sc.get('_lines', []):
            if ln['t0'] <= t < ln['t1']:
                spk = ln['speaker']
                if spk not in ('narrator', 'none') and spk != c['who']:
                    return False
                if spk == 'none' or (spk == 'narrator' and ci != 0):
                    return False
                if ln['env'] is not None:
                    i = int((t - ln['t0']) * self.fps)
                    return 0 <= i < len(ln['env']) and ln['env'][i] > 0.25
                return int(t * self.fps / 4) % 2 == 0
        return False

    def frame(self, sc, t, captions=True):
        W, H, k = self.W, self.H, self.k
        img = self.background(sc['bg']).copy().convert('RGBA')
        side, xs, box = self.layout(sc)
        show = sc.get('show') or {}
        dur = sc['duration']

        # ---- element
        if side:
            bx0, by0, bx1, by1 = [v * k for v in box]
            bw, bh = bx1 - bx0, by1 - by0
            p = self.progress(sc, t)
            el = self.element(sc, box[2] - box[0], box[3] - box[1], p)
            if el is not None:
                if sc['bg'] == 'notebook':                      # pencil reveal, left to right
                    r = EL.clamp((t - 0.1) / max(0.8, min(2.6, dur * 0.5)))
                    cut = int(el.width * r)
                    if cut > 0:
                        img.alpha_composite(el.crop((0, 0, cut, el.height)), (int(bx0), int(by0)))
                    if r < 1:
                        self._pencil(img, bx0 + cut, by0 + bh * (0.3 + 0.4 * (0.5 + 0.5 * math.sin(t * 9))))
                else:
                    a = EL.clamp(t / 0.35)
                    if show.get('enter', 'pop') == 'slide':
                        off = (1 - EL.ease_in_out(a)) * (W - bx0)
                        img.alpha_composite(el, (int(bx0 + off), int(by0)))
                    elif a < 1:
                        s = max(0.05, _ease_out_back(a))
                        e2 = el.resize((max(1, int(bw * s)), max(1, int(bh * s))), Image.BILINEAR)
                        img.alpha_composite(e2, (int(bx0 + (bw - e2.width) / 2), int(by0 + (bh - e2.height) / 2)))
                    else:
                        img.alpha_composite(el, (int(bx0), int(by0)))

        # ---- characters
        base_h = (560 if side else 660) * k
        for ci, c in enumerate(sc['chars']):
            who = c['who']
            h = base_h * float(c.get('size', 1.0)) * (0.5 if who == 'piggy' else 1.0)
            blink = ((t + ci * 1.3) % 3.7) < 0.12
            talk = self.talking(sc, t, ci, c)
            mood = c.get('mood', 'smile')
            spr, bb, kk = self.sprite(who, c.get('pose', 'idle'), mood, blink, talk, h)
            br = math.sin((t + ci) * 2 * math.pi * 0.8)
            sx, sy = 1 - 0.012 * br, 1 + 0.012 * br
            x = xs[ci] * W
            y = FLOOR_Y * k + 6 * k
            ent = c.get('enter')
            if ent in ('left', 'right') and t < 0.6:
                q = EL.ease_in_out(t / 0.6)
                x = (-spr.width if ent == 'left' else W + spr.width) * (1 - q) + x * q
                y -= abs(math.sin(t * math.pi * 5)) * 40 * k * (1 - q)
            elif ent == 'pop' and t < 0.4:
                s = max(0.05, _ease_out_back(t / 0.4))
                sx, sy = sx * s, sy * s
            if c.get('hop', mood == 'shock' or c.get('pose') == 'celebrate') and t < 0.35:
                y -= 60 * k * math.sin(math.pi * t / 0.35)
            if who == 'piggy' and show.get('type') == 'coin_drop':
                y, sx, sy = self._coin_drop(img, t, dur, x, y, spr, bb, kk, sx, sy)
            s2 = spr if (abs(sx - 1) < 1e-3 and abs(sy - 1) < 1e-3) else \
                spr.resize((max(1, int(spr.width * sx)), max(1, int(spr.height * sy))), Image.BILINEAR)
            img.alpha_composite(s2, (int(x - s2.width / 2), int(y - s2.height)))

        # ---- chapter tag, transition, subtitles
        if sc.get('chapter') and t < 2.8:
            self._chapter(img, sc['chapter'], t)
        if sc.get('transition') == 'fade' and t < 0.3:
            veil = Image.new('RGBA', img.size, CREAM + (int(255 * (1 - t / 0.3)),))
            img.alpha_composite(veil)
        if captions:
            txt = self.cue_at(sc['start'] + t)
            if txt:
                cap = self.caption_img(txt)
                img.alpha_composite(cap, (int((W - cap.width) / 2), int(H - cap.height - 40 * k)))
        return img.convert('RGB')

    def _pencil(self, img, x, y):
        k = self.k
        p = Pen(int(160 * k), int(160 * k), 2)
        s = k
        p.poly([(6 * s, 150 * s), (26 * s, 112 * s), (128 * s, 10 * s), (150 * s, 32 * s), (48 * s, 134 * s)],
               (255, 196, 61), INK, 4 * s)
        p.poly([(6 * s, 150 * s), (26 * s, 112 * s), (48 * s, 134 * s)], (240, 214, 170), INK, 3 * s)
        p.circle(10 * s, 146 * s, 5 * s, INK)
        im = p.done()
        img.alpha_composite(im, (int(x - 6 * k), int(y - 150 * k)))

    def _chapter(self, img, title, t):
        k = self.k
        a = min(1.0, t / 0.25, (2.8 - t) / 0.3)
        f = font('bold', int(34 * k))
        tw = f.getlength(title.upper())
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        x0, y0 = 40 * k, 36 * k
        d.rounded_rectangle((x0, y0, x0 + tw + 60 * k, y0 + 64 * k), int(32 * k), fill=GREEN + (int(235 * a),))
        d.text((x0 + 30 * k, y0 + 32 * k), title.upper(), font=f, fill=(255, 255, 255, int(255 * a)), anchor='lm')
        img.alpha_composite(lay)

    def _coin_drop(self, img, t, dur, x, y, spr, bb, kk, sx, sy):
        """A coin falls into Piggy Ben's slot at ~45% of the scene; the pig squashes on impact."""
        slot_x = x - spr.width / 2 + (350 - bb[0]) * kk
        slot_y = y - spr.height + (191 - bb[1]) * kk
        t_hit = dur * 0.48
        fall = 0.55
        r = 30 * self.k
        if t_hit - fall <= t < t_hit:
            q = (t - (t_hit - fall)) / fall
            cy = -r + (slot_y + r) * q * q
            p = Pen(int(r * 2 + 8), int(r * 2 + 8), 2)
            c = r + 4
            p.circle(c, c, r, GOLD, INK, r * 0.09)
            p.circle(c, c, r * 0.72, None, (214, 150, 30), r * 0.07)
            p.text((c, c + r * 0.05), '$', 'display', r * 1.05, (150, 98, 18), anchor='mm')
            im = p.done()
            img.alpha_composite(im, (int(slot_x - c), int(cy - c)))
        elif t_hit <= t < t_hit + 0.4:
            it = t - t_hit
            a = math.exp(-it * 9) * math.cos(it * 30)
            sx, sy = sx * (1 + 0.1 * a), sy * (1 - 0.1 * a)
        return y, sx, sy


def vertical(R, sc, t, hook_text, gt, total, end_text):
    """9:16 Short: the 16:9 frame in the middle, hook text on top, big subtitles below."""
    W, H = 1080, 1920
    v = Image.new('RGB', (W, H), CREAM)
    land = R.frame(sc, t, captions=False)
    land = land.resize((W, int(W * land.height / land.width)), Image.BILINEAR)
    v.paste(land, (0, 560))
    d = ImageDraw.Draw(v)
    title = hook_text if gt < 3.0 else ''
    if title:
        f = font('display', 96)
        d.text((W / 2, 300), title, font=f, fill=INK, anchor='mm')
    txt = R.cue_at(sc['start'] + t)
    if txt:
        f = font('semi', 68)
        words, lines, cur = txt.replace('*', '').split(), [], ''
        for wd in words:
            tr = (cur + ' ' + wd).strip()
            if f.getlength(tr) > W - 120 and cur:
                lines.append(cur)
                cur = wd
            else:
                cur = tr
        lines.append(cur)
        for i, ln in enumerate(lines):
            d.text((W / 2, 1360 + i * 86), ln, font=f, fill=INK, anchor='mm', stroke_width=0)
    if gt > total - 2.2:
        f = font('display', 84)
        d.rounded_rectangle((90, 1600, W - 90, 1760), 40, fill=GREEN)
        d.text((W / 2, 1680), end_text, font=f, fill=(255, 255, 255), anchor='mm')
    return v
