"""Frame composer: background + money element + mascots + chapter tag + subtitles.

Animation is cut-out style: mascots are cached sprites; life comes from breathing, blinking, lip flaps
driven by the voice loudness, hops, pop-in/slide-in elements, Ben's spiral notebook (a tilted page on the desk:
the page flips when the drawing goes on, slides in when the scene changes kind), and a coin dropping into Piggy Ben.
"""
import bisect
import math
import random
from PIL import Image, ImageDraw, ImageFilter
from engine.flatkit import Pen, font
from engine import charkit
import elements as EL
import sketch
import timeline

INK, MUTED, CREAM = (29, 33, 45), (112, 108, 100), (246, 241, 230)
GOLD, GREEN = (255, 196, 61), (46, 139, 87)
FLOOR_Y = 905
PAGE_SIDE = (640, 50, 1880, 900)          # notebook page beside the characters (design units)
PAGE_FULL = (230, 40, 1690, 905)          # notebook page when nobody is on screen
PAGE_IN = (96, 120, 40, 34)               # drawing area inset on the page: left, top, right, bottom
PAGE_TILT = -2.0                           # degrees (negative = clockwise)
SLIDE, FLIP = 0.45, 0.55                   # seconds for an element sliding in / a page turning


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
        elif name == 'notebook':                          # the desk the spiral notebook lies on
            p.vgrad((0, 0, W, H), '#F3E8D4', '#E6D5B8')
            p.rect((0, FLOOR_Y - 8, W, H), '#9A6B45')
            p.rect((0, FLOOR_Y - 14, W, FLOOR_Y), '#B07D53')
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
        is_sketch = sc['show'].get('type') == 'sketch'
        q = round(p * 240) / 240 if is_sketch else EL.quantize(sc['show'], p)   # the hand needs fine steps
        key = (sc['index'], q, int(w), int(h))
        if key not in self._el:
            if len(self._el) > 500:
                self._el.clear()
            tip = None
            if is_sketch:
                im, tip = sketch.render(sc['show'], w, h, q, S=self.S)
            else:
                im = EL.render(sc['show'], w, h, q, S=self.S)
            if im is not None and self.k != 1:
                im = im.resize((max(1, int(w * self.k)), max(1, int(h * self.k))), Image.LANCZOS)
            self._el[key] = (im, tip)
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
        if sc['bg'] == 'notebook' and side:              # the element sits on a spiral notebook page
            page = PAGE_SIDE if chars else PAGE_FULL
            box = (page[0] + PAGE_IN[0], page[1] + PAGE_IN[1], page[2] - PAGE_IN[2], page[3] - PAGE_IN[3])
        else:
            box = (700, 110, 1860, 890) if (side and chars) else (380, 110, 1540, 890)
        return side, xs, box

    def progress(self, sc, t):
        """Animation progress of the scene's element. Counting elements (money card / phone with a change)
        run while the line that announces the change is spoken; everything else builds over the scene."""
        show = sc.get('show') or {}
        lines = sc.get('_lines') or []
        if show.get('type') == 'sketch':                 # finish drawing at ~75% so the result can be read
            start = timeline.draw_start(sc)
            return EL.clamp((t - start) / max(1.2, sc['duration'] * 0.75 - start))
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
        hand_tip = None

        # ---- element
        if side and sc['bg'] == 'notebook':
            hand_tip = self._notebook(img, sc, t, box)
        elif side:
            bx0, by0, bx1, by1 = [v * k for v in box]
            bw, bh = bx1 - bx0, by1 - by0
            p = self.progress(sc, t)
            el, tip = self.element(sc, box[2] - box[0], box[3] - box[1], p)
            enter = sc.get('_enter') or 'pop'
            if enter == 'slide' and t < SLIDE:                    # a new kind of element slides in from the right
                q = EL.ease_in_out(t / SLIDE)
                bx0 += (1 - q) * (W - bx0 + 40 * k)
            if el is not None and show.get('type') == 'sketch':
                img.alpha_composite(el, (int(bx0), int(by0)))   # draws itself stroke by stroke
                hand_tip = (bx0 + tip[0] * k, by0 + tip[1] * k) if tip else None
            elif el is not None:
                a = EL.clamp(t / 0.35)
                if enter == 'pop' and a < 1:
                    s = max(0.05, _ease_out_back(a))
                    e2 = el.resize((max(1, int(bw * s)), max(1, int(bh * s))), Image.BILINEAR)
                    img.alpha_composite(e2, (int(bx0 + (bw - e2.width) / 2), int(by0 + (bh - e2.height) / 2)))
                elif bx0 < W:
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

        if hand_tip:
            self._hand(img, hand_tip)

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

    def _hand(self, img, tip):
        """The drawing hand (marker tip on `tip`), its arm coming in from the bottom-right corner."""
        k = self.k
        x0, y0 = int(tip[0] - 60 * k), int(tip[1] - 60 * k)
        w, h = self.W - x0, self.H - y0
        if w <= 0 or h <= 0:
            return
        p = Pen(int(w / k) + 1, int(h / k) + 1, 1 if self.S == 1 else 2)
        sketch.draw_hand(p, 60, 60)
        im = p.done()
        if k != 1:
            im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.BILINEAR)
        img.alpha_composite(im, (x0, y0))

    # ------------------------------------------------------------ Ben's notebook
    def _page(self, pw, ph):
        """A blank spiral notebook page (pw x ph pixels at output scale), cached."""
        key = ('page', pw, ph)
        if key not in self._bg:
            k = self.k
            p = Pen(int(pw / k) + 1, int(ph / k) + 1, 2)
            w, h = p.w, p.h
            top = 38                                          # room for the spiral rings
            p.rect((0, top, w, h), '#FFFDF6', (205, 195, 172), 3, r=14)
            for y in range(top + 96, h - 16, 46):
                p.line([(18, y), (w - 18, y)], 2, (175, 205, 235), caps=False)
            p.line([(PAGE_IN[0] - 28, top + 6), (PAGE_IN[0] - 28, h - 6)], 3, (232, 120, 120), caps=False)
            for x in range(54, w - 40, 60):
                p.circle(x + 11, top + 14, 9, (120, 110, 100))         # punched hole
                p.ellipse((x, 6, x + 22, top + 26), None, (90, 92, 104), 6)   # the ring over it
            im = p.done()
            self._bg[key] = im.resize((pw, ph), Image.LANCZOS) if im.size != (pw, ph) else im
        return self._bg[key]

    def _notebook(self, img, sc, t, box):
        """Draws the scene's page (element on it, tilted, with a shadow); returns the pencil tip or None."""
        k, W = self.k, self.W
        page = PAGE_SIDE if sc['chars'] else PAGE_FULL
        px0, py0, px1, py1 = [int(v * k) for v in page]
        pw, ph = px1 - px0, py1 - py0
        canvas = self._page(pw, ph).copy()
        show = sc['show']
        dur = sc['duration']
        ix, iy = PAGE_IN[0] * k, PAGE_IN[1] * k
        p = self.progress(sc, t)
        el, tip = self.element(sc, box[2] - box[0], box[3] - box[1], p)
        local_tip = None
        if el is not None and show.get('type') == 'sketch':
            canvas.alpha_composite(el, (int(ix), int(iy)))
            local_tip = (ix + tip[0] * k, iy + tip[1] * k) if tip else None
        elif el is not None:                                      # other elements: a pencil reveal, left to right
            r = EL.clamp((t - 0.6) / max(0.8, min(2.6, dur * 0.5)))
            cut = int(el.width * r)
            if cut > 0:
                canvas.alpha_composite(el.crop((0, 0, cut, el.height)), (int(ix), int(iy)))
            if 0 < r < 1:
                local_tip = (ix + cut, iy + el.height * (0.3 + 0.4 * (0.5 + 0.5 * math.sin(t * 9))))
        enter = sc.get('_enter')
        if enter == 'flip' and t < FLIP:
            self._flip(canvas, t / FLIP)
        rot = canvas.rotate(PAGE_TILT, resample=Image.BILINEAR, expand=True)
        ox = px0 - (rot.width - pw) / 2
        oy = py0 - (rot.height - ph) / 2
        if enter == 'slide' and t < SLIDE:                        # the notebook slides in from the right
            ox += (1 - EL.ease_in_out(t / SLIDE)) * (W - ox + 40 * k)
        shadow = self._page_shadow(rot)
        img.alpha_composite(shadow, (max(0, int(ox + 14 * k)), max(0, int(oy + 18 * k))),
                            (max(0, -int(ox + 14 * k)), max(0, -int(oy + 18 * k))))
        img.alpha_composite(rot, (max(0, int(ox)), max(0, int(oy))), (max(0, -int(ox)), max(0, -int(oy))))
        if local_tip is None or (enter == 'slide' and t < SLIDE):
            return None
        # the same rotation for the pencil tip (PIL turns counter-clockwise for a positive angle)
        a = math.radians(PAGE_TILT)
        cx, cy = pw / 2, ph / 2
        dx, dy = local_tip[0] - cx, local_tip[1] - cy
        rx = dx * math.cos(a) + dy * math.sin(a)
        ry = -dx * math.sin(a) + dy * math.cos(a)
        return (ox + rot.width / 2 + rx, oy + rot.height / 2 + ry)

    def _page_shadow(self, rot):
        key = ('shadow', rot.size)
        if key not in self._bg:
            a = rot.getchannel('A').point(lambda v: 70 if v > 20 else 0)
            sh = Image.new('RGBA', rot.size, (0, 0, 0, 0))
            sh.putalpha(a.filter(ImageFilter.GaussianBlur(14 * self.k)))
            self._bg[key] = sh
        return self._bg[key]

    def _flip(self, canvas, q):
        """The previous page (blank) lifts and turns from right to left, revealing this one."""
        q = EL.ease_in_out(q)
        W, H = canvas.size
        old = self._page(W, H)
        edge = int(W * (1 - q))
        if edge <= 0:
            return
        top = int(38 * self.k)
        canvas.alpha_composite(old.crop((0, 0, edge, H)), (0, 0))
        curl = W * 0.10 * math.sin(math.pi * q) + 2
        lay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for i in range(10):                                              # shadow cast by the lifted page
            d.rectangle((edge + curl + i * 4 * self.k, top, edge + curl + (i + 1) * 4 * self.k, H),
                        fill=(0, 0, 0, int(22 * (1 - i / 10))))
        d.polygon([(edge, top), (edge + curl, top - 6), (edge + curl * 0.8, H), (edge, H)], fill=(236, 230, 214, 255))
        d.line([(edge + curl, top - 6), (edge + curl * 0.8, H)], fill=(200, 192, 172, 255), width=max(1, int(3 * self.k)))
        canvas.alpha_composite(lay)

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
