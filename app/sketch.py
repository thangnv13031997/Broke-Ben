"""Ben's Notebook: hand-drawn charts, drawn stroke by stroke by a hand holding a marker.

A sketch is a list of drawing operations (lines, written text, fills). Progress p (0..1) is mapped onto the
total "ink length", so the drawing grows in a natural order: title, axes, data, labels. The hand sits on
the tip of whatever is being drawn. Lines get a small deterministic wobble so they look hand-made.

Kinds (show.type = "sketch", show.kind = ...):
  line  : title, labels [..], series [{name, values, color}], prefix  -- or invest {monthly, rate, years, start_age}
  bars  : title, items [[label, value, color?], ...], prefix
  pie   : title, items [[label, value], ...]   (shares are computed)
  flow  : title, steps ["Paycheck +$3,000", "Rent -$1,450", ...]  (boxes joined by arrows)
"""
import math
from engine.flatkit import Pen
import elements as EL
import money_math

INK = (38, 44, 62)
COL = {'green': (46, 139, 87), 'red': (214, 69, 69), 'gold': (214, 150, 30), 'blue': (52, 110, 190),
       'ink': INK, 'grey': (130, 130, 130)}
PIE = ['green', 'red', 'gold', 'blue', 'grey']
SKIN, SKIN_SH, HOOD, HOOD_SH = (255, 217, 184), (238, 184, 148), (63, 163, 107), (44, 128, 82)
OUTLINE = (43, 34, 51)


# ---------------------------------------------------------------- geometry
def _wobble(pts, seed, amp=1.6, step=18):
    """Subdivide a polyline and nudge it sideways with smooth noise, like a real marker stroke."""
    out = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L / step))
        nx, ny = (-(y1 - y0) / L, (x1 - x0) / L) if L else (0, 0)
        for k in range(n):
            t = k / n
            w = amp * math.sin(seed * 1.7 + (i * n + k) * 0.9) * math.sin(seed * 0.3 + (i * n + k) * 0.37)
            out.append((x0 + (x1 - x0) * t + nx * w, y0 + (y1 - y0) * t + ny * w))
    out.append(pts[-1])
    return out


def _length(pts):
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))


def _partial(pts, frac):
    total = _length(pts) * frac
    out, acc = [pts[0]], 0.0
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        if acc + seg >= total:
            t = (total - acc) / seg if seg else 0
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            return out
        out.append((x1, y1))
        acc += seg
    return out


def _circle_pts(cx, cy, r, a0=-90, a1=270, n=72):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def _rrect_pts(x0, y0, x1, y1, r=18):
    pts = []
    for cx, cy, a in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        pts += _circle_pts(cx, cy, r, a, a + 90, 6)
    return pts + [pts[0]]


# ---------------------------------------------------------------- building the ops
class Ops:
    def __init__(self):
        self.ops = []
        self.seed = 1

    def line(self, pts, width=6, color=INK, wobble=True):
        self.seed += 1
        self.ops.append(('line', _wobble(pts, self.seed) if wobble else pts, width, color))

    def arrow(self, a, b, width=6, color=INK):
        self.line([a, b], width, color)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        for d in (2.6, -2.6):
            self.line([b, (b[0] + 22 * math.cos(ang + d), b[1] + 22 * math.sin(ang + d))], width, color, False)

    def text(self, x, y, s, size=34, color=INK, anchor='l'):
        self.ops.append(('text', x, y, str(s), size, color, anchor))

    def fill(self, poly, color, alpha=70):
        self.ops.append(('fill', poly, color + (alpha,)))


def _title(o, spec, w):
    if spec.get('title'):
        o.text(50, 58, spec['title'], 58)
        tw = min(w - 100, 26 * len(spec['title']))
        o.line([(48, 92), (50 + tw, 96)], 5, COL['gold'])


def _nice_top(vmax):
    mag = 10 ** int(math.log10(max(vmax, 1)))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if vmax <= m * mag:
            return m * mag
    return 10 * mag


def build(spec, w, h):
    o = Ops()
    kind = spec.get('kind', 'line')
    prefix = spec.get('prefix', '$')
    _title(o, spec, w)
    if kind == 'bars':
        items = spec.get('items') or [['A', 1], ['B', 2]]
        X0, X1, Y0, Y1 = 90, w - 60, h - 110, 170
        vmax = _nice_top(max(float(it[1]) for it in items))
        o.arrow((X0, Y0), (X0, Y1 - 20), 6)
        o.line([(X0, Y0), (X1, Y0)], 6)
        n = len(items)
        slot = (X1 - X0) / n
        bw = min(150, slot * 0.6)
        for i, it in enumerate(items):
            lab, val = str(it[0]), float(it[1])
            col = COL.get(it[2] if len(it) > 2 else ('red' if i == spec.get('highlight') else 'green'), COL['green'])
            cx = X0 + slot * (i + 0.5)
            top = Y0 - (Y0 - Y1) * val / vmax
            rect = [(cx - bw / 2, Y0), (cx - bw / 2, top), (cx + bw / 2, top), (cx + bw / 2, Y0)]
            o.line(rect, 6, INK)
            o.fill(rect, col, 110)
            o.text(cx, top - 26, EL.money(val, prefix), 40, col, 'c')
            o.text(cx, Y0 + 40, lab, 32, INK, 'c')
    elif kind == 'pie':
        items = spec.get('items') or [['A', 1], ['B', 1]]
        total = sum(float(it[1]) for it in items) or 1
        cx, cy, r = w * 0.36, h * 0.56, min(w, h) * 0.3
        o.line(_circle_pts(cx, cy, r), 6)
        a = -90.0
        for i, it in enumerate(items):
            share = float(it[1]) / total
            a1 = a + 360 * share
            col = COL[PIE[i % len(PIE)]]
            wedge = [(cx, cy)] + _circle_pts(cx, cy, r, a, a1, max(3, int(60 * share))) + [(cx, cy)]
            o.line([(cx, cy), (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))], 5)
            o.fill(wedge, col, 120)
            am = math.radians((a + a1) / 2)
            o.text(cx + r * 0.62 * math.cos(am), cy + r * 0.62 * math.sin(am), f'{share:.0%}', 40, INK, 'c')
            ly = 190 + i * 74
            o.fill(_rrect_pts(w * 0.7, ly - 20, w * 0.7 + 40, ly + 20, 8), col, 200)
            o.text(w * 0.7 + 56, ly, f'{it[0]} ({EL.money(float(it[1]), prefix)})', 34, INK, 'l')
            a = a1
    elif kind == 'flow':
        steps = spec.get('steps') or ['Paycheck', 'Bills', 'Left']
        n = len(steps)
        per_row = n if n <= 4 else math.ceil(n / 2)
        rows = math.ceil(n / per_row)
        bw = min(300, (w - 100 - (per_row - 1) * 70) / per_row)
        bh = 120
        prev = None
        for i, s in enumerate(steps):
            r_, c = divmod(i, per_row)
            if r_ % 2 == 1:
                c = per_row - 1 - c                       # snake layout keeps arrows short
            x0 = 50 + c * (bw + 70)
            y0 = 190 + r_ * (bh + 120) + (0 if rows > 1 else 140)
            col = COL['red'] if '-' in s.split()[-1] else (COL['green'] if '+' in s else INK)
            box = _rrect_pts(x0, y0, x0 + bw, y0 + bh)
            if prev:
                px0, py0 = prev
                if py0 == y0:
                    a_, b_ = ((px0 + bw, y0 + bh / 2), (x0 - 8, y0 + bh / 2)) if x0 > px0 else \
                        ((px0, y0 + bh / 2), (x0 + bw + 8, y0 + bh / 2))
                else:
                    a_, b_ = (px0 + bw / 2, py0 + bh), (x0 + bw / 2, y0 - 8)
                o.arrow(a_, b_, 6)
            o.line(box, 6, INK)
            o.fill(box, col, 40)
            words = s.split()
            if len(words) > 1 and words[-1][:1] in '+-$':
                o.text(x0 + bw / 2, y0 + 44, ' '.join(words[:-1]), 34, INK, 'c')
                o.text(x0 + bw / 2, y0 + 88, words[-1], 40, col, 'c')
            else:
                o.text(x0 + bw / 2, y0 + bh / 2, s, 36, col, 'c')
            prev = (x0, y0)
    else:                                                           # line chart
        series = spec.get('series')
        labels = spec.get('labels')
        if not series and spec.get('invest'):
            iv = spec['invest']
            rows = money_math.invest(float(iv.get('monthly', 200)), float(iv.get('rate', 0.07)),
                                     int(iv.get('years', 30)), 0.0, iv.get('compounding', 'monthly'))
            series = [{'name': 'Your money', 'values': [0.0] + [r_[2] for r_ in rows], 'color': 'green'},
                      {'name': 'You put in', 'values': [0.0] + [r_[1] for r_ in rows], 'color': 'ink'}]
            age = iv.get('start_age')
            labels = [(age + i) if age is not None else i for i in range(len(series[0]['values']))]
        series = series or [{'name': '', 'values': [0, 1]}]
        X0, X1, Y0, Y1 = 150, w - 70, h - 110, 170
        vmax = _nice_top(max(max(s['values']) for s in series))
        o.arrow((X0, Y0), (X0, Y1 - 30), 6)
        o.arrow((X0, Y0), (X1 + 20, Y0), 6)
        for k in (0.5, 1.0):
            y = Y0 - (Y0 - Y1) * k
            o.line([(X0 - 12, y), (X0 + 12, y)], 5)
            v = vmax * k
            lab = prefix + (f'{v / 1e6:g}M' if v >= 1e6 else f'{v / 1000:g}K' if v >= 1000 else f'{v:g}')
            o.text(X0 - 20, y, lab, 36, INK, 'r')
        n = len(series[0]['values'])
        X = lambda i: X0 + (X1 - X0) * i / max(1, n - 1)
        if labels:
            for i in (0, (n - 1) // 2, n - 1):
                o.text(X(i), Y0 + 40, labels[i], 36, INK, 'c')
        for j, s in enumerate(series):
            col = COL.get(s.get('color', 'green'), COL['green'])
            pts = [(X(i), Y0 - (Y0 - Y1) * v / vmax) for i, v in enumerate(s['values'])]
            o.line(pts, 8 if j == 0 else 6, col)
            ex, ey = pts[-1]
            o.fill(_circle_pts(ex, ey, 10, n=16), col, 255)
            o.text(ex - 14, ey + (-34 if j == 0 else 30), f'{s.get("name", "")}: {EL.money(s["values"][-1], prefix)}',
                   44 if j == 0 else 36, col if j == 0 else INK, 'r')
    return o.ops


# ---------------------------------------------------------------- drawing
def _op_len(op, pen):
    if op[0] == 'line':
        return _length(op[1])
    if op[0] == 'text':
        return pen.text_w(op[3], 'hand', op[4]) * 0.9
    return 120.0


def _text_left(pen, x, s, size, anchor):
    tw = pen.text_w(s, 'hand', size)
    return x - tw if anchor == 'r' else x - tw / 2 if anchor == 'c' else x


# The drawing hand, traced from a whiteboard-style reference (units: reference pixels, pencil tip at REF_TIP).
REF_TIP = (213, 420)
HAND_SCALE = 0.27
_PALM = [(342, 392), (385, 370), (450, 334), (515, 296), (548, 286), (590, 296), (660, 330), (722, 360),
         (790, 388), (818, 412), (832, 455), (846, 545), (872, 650), (930, 740), (1000, 800),
         (800, 950), (760, 830), (705, 778), (620, 740), (540, 680), (470, 615), (420, 600), (370, 598),
         (346, 570), (342, 520), (334, 455)]
_FINGERS = [((370, 522), (38, 25)), ((372, 566), (34, 23)), ((398, 600), (30, 19))]
_INDEX = [(338, 400), (352, 384), (392, 374), (440, 384), (474, 410), (440, 428), (380, 420), (346, 414)]
_THUMB = [(318, 430), (330, 410), (360, 404), (410, 422), (452, 456), (474, 496), (452, 516), (404, 514),
          (362, 490), (330, 464)]
_SLEEVE = [(985, 755), (1555, 1450), (1330, 1640), (760, 925)]         # hoodie sleeve, runs off the frame
_CUFF = [(985, 755), (1035, 815), (810, 985), (760, 925)]
_CREASES = [[(536, 300), (548, 322)], [(430, 372), (446, 388)], [(372, 425), (396, 436)],
            [(520, 660), (560, 682)], [(352, 540), (372, 538)], [(356, 578), (378, 576)]]
PENCIL, PENCIL_SH, WOOD, LEAD = (255, 196, 61), (226, 160, 40), (240, 214, 170), (38, 44, 62)


def draw_hand(pen, x, y):
    """A hand holding a pencil, whiteboard-animation style; the pencil tip sits on (x, y).
    The arm (green hoodie sleeve) comes in from the bottom right. Drawn by the scene on the full frame so the
    arm is never clipped by the chart box."""
    s = HAND_SCALE

    def P(pt):
        return (x + (pt[0] - REF_TIP[0]) * s, y + (pt[1] - REF_TIP[1]) * s)

    def shape(pts, fill, w=3):
        pen.poly([P(q) for q in pts], fill, OUTLINE, w)

    # pencil frame: u along the pencil (tip -> end), v across it
    ex, ey = 880, 506
    L = math.hypot(ex - REF_TIP[0], ey - REF_TIP[1])
    du = ((ex - REF_TIP[0]) / L, (ey - REF_TIP[1]) / L)
    dv = (-du[1], du[0])

    def Q(u, v):
        return (REF_TIP[0] + du[0] * u + dv[0] * v, REF_TIP[1] + du[1] * u + dv[1] * v)

    shape(_PALM, SKIN)
    pen.poly([P(q) for q in [(470, 615), (540, 680), (620, 740), (705, 778), (760, 830), (800, 950),
                             (830, 925), (790, 800), (700, 740), (600, 690), (520, 630)]], SKIN_SH)
    shape(_SLEEVE, HOOD)
    pen.poly([P(q) for q in [(790, 960), (1360, 1620), (1420, 1570), (840, 920)]], HOOD_SH)
    shape(_CUFF, HOOD_SH)
    for (cx, cy), (rx, ry) in _FINGERS:
        shape([(cx + rx * math.cos(t), cy + ry * math.sin(t)) for t in (i * math.pi / 14 for i in range(28))],
              SKIN, 2.5)
    # the pencil: lead, sharpened wood, yellow body with a shaded lower half
    shape([Q(0, 0), Q(92, -30), Q(92, 30)], WOOD, 2.5)
    pen.poly([P(Q(0, 0)), P(Q(30, -10)), P(Q(30, 10))], LEAD)
    shape([Q(92, -30), Q(L, -30), Q(L, 30), Q(92, 30)], PENCIL, 2.5)
    pen.poly([P(Q(94, 8)), P(Q(L - 2, 8)), P(Q(L - 2, 28)), P(Q(94, 28))], PENCIL_SH)
    shape(_INDEX, SKIN, 2.5)
    shape(_THUMB, SKIN, 2.5)
    for c in _CREASES:
        pen.line([P(q) for q in c], 1.8, OUTLINE)


def render(spec, w, h, p, S=2):
    """Returns (RGBA image w x h, marker tip (x, y) in box coordinates or None when finished)."""
    pen = Pen(int(w), int(h), S)
    ops = build(spec, w, h)
    lens = [_op_len(op, pen) for op in ops]
    total = sum(lens) or 1
    p = max(0.0, min(1.0, p))
    ink = total * p + (1.0 if p >= 1.0 else 0.0)        # at p = 1 everything is fully drawn
    tip = None
    fills = pen.layer()
    for op, L in zip(ops, lens):
        if ink <= 0:
            break
        frac = 1.0 if (not L or ink >= L - 1e-6) else ink / L
        ink -= L
        if op[0] == 'line':
            pts = op[1] if frac >= 1 else _partial(op[1], frac)
            if len(pts) >= 2:
                pen.line(pts, op[2], op[3])
            tip = pts[-1]
        elif op[0] == 'text':
            _, x, y, s, size, col, anchor = op
            left = _text_left(pen, x, s, size, anchor)
            n = len(s) if frac >= 1 else int(len(s) * frac)
            if n:
                pen.text((left, y), s[:n], 'hand', size, col, anchor='lm')
            tip = (left + pen.text_w(s[:n], 'hand', size), y + size * 0.3)
        else:
            col = op[2][:3] + (int(op[2][3] * frac),)
            fills.poly(op[1], col)
            xs = [q[0] for q in op[1]]
            ys = [q[1] for q in op[1]]
            tip = (sum(xs) / len(xs), sum(ys) / len(ys))
    base = pen.layer()                                      # fills sit under the ink
    base.paste(fills)
    base.paste(pen)
    return base.done(), (tip if p < 1.0 else None)
