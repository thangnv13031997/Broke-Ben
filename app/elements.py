"""On-screen money elements. Each draws into its own box and depends only on `p` (0..1 progress through
its animation), so frames can be cached. Every number shown is computed here, never typed by hand.
"""
import math
from PIL import ImageDraw, ImageFilter
from engine.flatkit import Pen
import money_math

INK, MUTED = (29, 33, 45), (112, 108, 100)
GREEN, RED, GOLD = (46, 139, 87), (214, 69, 69), (255, 196, 61)
CARD, LINE = (255, 255, 252), (226, 220, 208)
COLORS = {'green': GREEN, 'red': RED, 'gold': (196, 140, 20), 'ink': INK}


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_in_out(t):
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_out_back(t):
    t = clamp(t)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def money(v, prefix='$', decimals=0):
    s = f'{abs(v):,.{decimals}f}'
    return ('-' if v < 0 else '') + prefix + s


def seg(p, a, b):
    """Progress of p inside the window [a, b]."""
    return clamp((p - a) / max(1e-6, b - a))


def fit(pen, text, kind, size, max_w):
    while size > 14 and pen.text_w(text, kind, size) > max_w:
        size -= 2
    return size


def _card(pen, x0, y0, x1, y1, r=34):
    pen.rect((x0 + 10, y0 + 14, x1 + 10, y1 + 14), (0, 0, 0, 40), r=r)
    pen.rect((x0, y0, x1, y1), CARD, INK, 5, r=r)


# ---------------------------------------------------------------- elements
def money_card(pen, w, h, spec, p):
    """A money number on a card. style: sticker (default), tag (money out: red), bill (money in: green), plain."""
    v0 = float(spec.get('value', 0))
    v1 = float(spec.get('to', v0))
    k = ease_in_out(seg(p, 0.0, 0.9))           # p is timed to the line that announces the change
    v = v0 + (v1 - v0) * k
    col = spec.get('color', 'auto')
    if col == 'auto':
        col = RED if (v1 < v0 and k > 0.02) else GREEN
    else:
        col = COLORS.get(col, GREEN)
    label = spec.get('to_label') if (v1 != v0 and k > 0.5 and spec.get('to_label')) else spec.get('label', '')
    txt = money(v, spec.get('prefix', '$'), int(spec.get('decimals', 0)))
    note = spec.get('note', '')
    style = card_style(spec)
    if style == 'tag':
        _price_tag(pen, w, h, label, txt, note, col, p)
    elif style == 'bill':
        _bill(pen, w, h, label, txt, note, p)
    elif style == 'plain':
        cw, ch = min(w, 760), min(h, 420)
        x0, y0 = (w - cw) / 2, (h - ch) / 2
        _card(pen, x0, y0, x0 + cw, y0 + ch)
        if label:
            pen.text((w / 2, y0 + 78), label.upper(), 'bold', fit(pen, label.upper(), 'bold', 44, cw - 80), MUTED,
                     anchor='mm')
        pen.text((w / 2, y0 + ch * 0.58), txt, 'display', fit(pen, txt, 'display', 190, cw - 80), col, anchor='mm')
        if note:
            pen.text((w / 2, y0 + ch - 50), note, 'body', fit(pen, note, 'body', 34, cw - 80), MUTED, anchor='mm')
    else:
        _sticker(pen, w, h, label, txt, note, col)


def card_style(spec):
    """Picks the look of a money card from what it shows; `style` in the script overrides it."""
    st = spec.get('style')
    if st in ('sticker', 'tag', 'bill', 'plain'):
        return st
    if 'to' in spec:
        return 'sticker'                        # counting numbers stay on the sticker
    return {'red': 'tag', 'green': 'bill'}.get(spec.get('color'), 'sticker')


_STATIC = {}


def _cached_layer(pen, key, draw):
    """A Pen layer whose drawing never changes during the animation, drawn once and reused."""
    key = (key, pen.w, pen.h, pen.S)
    if key not in _STATIC:
        if len(_STATIC) > 40:
            _STATIC.clear()
        lay = pen.layer()
        draw(lay)
        _STATIC[key] = lay.img
    lay = pen.layer()
    lay.img = _STATIC[key].copy()
    lay.d = ImageDraw.Draw(lay.img)
    return lay


def _soft_shadow(pen, shape, rotate=0, blur=10, alpha=60, off=(12, 16)):
    sh = pen.layer()
    sh.poly([(x + off[0], y + off[1]) for x, y in shape], (0, 0, 0, alpha))
    pen.paste(sh, blur=blur, rotate=rotate)


def _sticker(pen, w, h, label, txt, note, col):
    """Bold sticker: thick outline, hard offset shadow, coloured tab with the label, slightly tilted."""
    cw, ch = min(w - 60, 760), min(h - 60, 440)
    x0, y0 = (w - cw) / 2, (h - ch) / 2
    lay = pen.layer()
    lay.rect((x0 + 20, y0 + 22, x0 + cw + 20, y0 + ch + 22), INK, r=30)
    lay.rect((x0, y0, x0 + cw, y0 + ch), (255, 255, 255), INK, 6, r=30)
    tab = 112
    lay.rect((x0, y0, x0 + cw, y0 + tab), col, INK, 6, r=30)
    lay.rect((x0 + 3, y0 + tab - 40, x0 + cw - 3, y0 + tab), col)
    lay.line([(x0, y0 + tab), (x0 + cw, y0 + tab)], 6, INK, caps=False)
    lab = (label or '').upper()
    if lab:
        lay.text((w / 2, y0 + tab / 2 + 2), lab, 'display', fit(lay, lab, 'display', 68, cw - 70), (255, 255, 255),
                 anchor='mm')
    body = ch - tab
    lay.text((w / 2, y0 + tab + body * (0.44 if note else 0.5)), txt, 'display',
             fit(lay, txt, 'display', 190, cw - 80), col, anchor='mm')
    if note:
        lay.text((w / 2, y0 + ch - 48), note, 'semi', fit(lay, note, 'semi', 38, cw - 80), MUTED, anchor='mm')
    pen.paste(lay, rotate=-3)


def _price_tag(pen, w, h, label, txt, note, col, p):
    """A price tag on a string that swings in and settles: for money going out."""
    tw, th = min(w - 120, 820), min(h - 200, 400)
    x0, y0 = (w - tw) / 2 + 30, (h - th) / 2 + 40
    hole = (x0 + 80, y0 + th / 2)
    shape = [(x0 + 150, y0), (x0 + tw - 20, y0), (x0 + tw, y0 + 20), (x0 + tw, y0 + th - 20), (x0 + tw - 20, y0 + th),
             (x0 + 150, y0 + th), (x0, y0 + th / 2)]
    swing = 7 + 9 * math.exp(-8 * p) * math.cos(22 * p)

    def draw_shadow(sh):
        sh.poly([(x + 12, y + 16) for x, y in shape], (0, 0, 0, 60))
        sh.img = sh.img.filter(ImageFilter.GaussianBlur(10 * sh.S))

    def draw_tag(lay):
        lay.line([hole, (hole[0] - 160, 0)], 5, INK)               # the string goes up out of the box
        lay.poly(shape, (255, 238, 236) if col == RED else (238, 248, 240), INK, 6)
        lay.circle(hole[0], hole[1], 26, (246, 241, 230), INK, 5)
        lay.line([(x0 + 184, y0 + 40), (x0 + tw - 40, y0 + 40)], 3,
                 (240, 190, 190) if col == RED else (190, 225, 200), caps=False)
        head = ' · '.join(x for x in ((label or '').upper(), (note or '').upper()) if x)
        cx = x0 + 150 + (tw - 170) / 2
        if head:
            lay.text((cx, y0 + 100), head, 'bold', fit(lay, head, 'bold', 44, tw - 220), shade_of(col), anchor='mm')
        lay.text((cx, y0 + th * 0.62), txt, 'display', fit(lay, txt, 'display', 190, tw - 220), col, anchor='mm')

    key = ('tag', label, txt, note, col)
    pen.paste(_cached_layer(pen, key + ('shadow',), draw_shadow), rotate=swing)
    pen.paste(_cached_layer(pen, key, draw_tag), rotate=swing, center=hole)


def _bill(pen, w, h, label, txt, note, p):
    """A banknote: for money coming in or money kept."""
    bw, bh = min(w - 60, 900), min(h - 80, 440)
    x0, y0 = (w - bw) / 2, (h - bh) / 2
    dark, light = (36, 110, 70), (214, 236, 214)
    _soft_shadow(pen, [(x0, y0), (x0 + bw, y0), (x0 + bw, y0 + bh), (x0, y0 + bh)])
    pen.rect((x0, y0, x0 + bw, y0 + bh), light, dark, 8, r=18)
    pen.rect((x0 + 26, y0 + 26, x0 + bw - 26, y0 + bh - 26), None, dark, 3, r=10)
    for i in range(14):                                         # engraved rings behind the number
        pen.circle(w / 2, y0 + bh / 2 + 20, 60 + i * 7, None, (160, 200, 168), 1.5)
    for cx, cy in ((x0 + 70, y0 + 70), (x0 + bw - 70, y0 + 70), (x0 + 70, y0 + bh - 70), (x0 + bw - 70, y0 + bh - 70)):
        pen.text((cx, cy), '$', 'display', 60, dark, anchor='mm')
    lab = (label or '').upper()
    if lab:
        pen.text((w / 2, y0 + 62), lab, 'bold', fit(pen, lab, 'bold', 40, bw - 220), dark, anchor='mm')
    pen.text((w / 2, y0 + bh / 2 + 20), txt, 'display', fit(pen, txt, 'display', 170, bw - 200), GREEN, anchor='mm',
             stroke=6, stroke_fill=light)
    pen.text((w / 2, y0 + bh - 66), (note or 'THE UNITED STATES OF BEN').upper(), 'semi', 30, dark, anchor='mm')


def shade_of(col):
    return tuple(int(c * 0.7) for c in col[:3])


def big_text(pen, w, h, spec, p):
    text = spec.get('text', '')
    col = COLORS.get(spec.get('color', 'ink'), INK)
    size = fit(pen, text, 'display', int(spec.get('size', 200)), w - 60)
    pen.text((w / 2, h * 0.45), text, 'display', size, col, anchor='mm')
    if spec.get('sub'):
        pen.text((w / 2, h * 0.45 + size * 0.75), spec['sub'], 'semi', fit(pen, spec['sub'], 'semi', 52, w - 80),
                 MUTED, anchor='mm')


def _line_chart(pen, w, h, p, title, sub, xlabels, series, prefix='$'):
    pen.rect((0, 0, w, h), CARD, INK, 5, r=30)
    pen.text((50, 44), title, 'bold', fit(pen, title, 'bold', 46, w - 100), INK)
    if sub:
        pen.text((50, 106), sub, 'body', fit(pen, sub, 'body', 30, w - 100), MUTED)
    X0, X1, Y0, Y1 = 150, w - 60, h - 90, 175
    vmax = max(max(s['values']) for s in series) or 1
    mag = 10 ** int(math.log10(vmax))
    step = mag if vmax / mag <= 5 else 2 * mag
    if vmax / step < 3:
        step /= 2
    top = math.ceil(vmax / step) * step
    Y = lambda v: Y0 - (Y0 - Y1) * v / top
    n = len(series[0]['values'])
    X = lambda i: X0 + (X1 - X0) * i / max(1, n - 1)
    v = 0.0
    while v <= top + 1e-9:
        pen.line([(X0, Y(v)), (X1, Y(v))], 1.5, LINE, caps=False)
        lab = money(v, prefix) if v < 1000 else prefix + (f'{v / 1e6:g}M' if v >= 1e6 else f'{v / 1000:g}K')
        pen.text((X0 - 16, Y(v)), lab, 'body', 26, MUTED, anchor='rm')
        v += step
    if xlabels:
        every = max(1, round((n - 1) / 4))
        for i in range(0, n, every):
            pen.text((X(i), Y0 + 18), str(xlabels[i]), 'body', 26, MUTED, anchor='mt')
    k = ease_in_out(seg(p, 0.05, 0.85))
    last = (n - 1) * k
    for s in series:
        col = COLORS.get(s.get('color', 'green'), GREEN)
        pts = [(X(i), Y(val)) for i, val in enumerate(s['values']) if i <= last]
        if last < n - 1 and int(last) + 1 < n:                    # partial last segment
            i = int(last)
            f = last - i
            a, b = s['values'][i], s['values'][i + 1]
            pts.append((X(i + f), Y(a + (b - a) * f)))
        if len(pts) >= 2:
            pen.line(pts, 6 if s is series[0] else 4, col)
    if k >= 0.999:
        for j, s in enumerate(series):
            col = COLORS.get(s.get('color', 'green'), GREEN)
            x, y = X(n - 1), Y(s['values'][-1])
            pen.circle(x, y, 10, col, CARD, 4)
            lab = f'{s.get("name", "")}: {money(s["values"][-1], prefix)}'
            dy = -16 if j == 0 else 18
            pen.text((x - 16, y + dy), lab, 'bold' if j == 0 else 'semi', 34 if j == 0 else 28,
                     INK if j == 0 else MUTED, anchor='rb' if j == 0 else 'rt')


def invest_chart(pen, w, h, spec, p):
    monthly, rate, years = float(spec.get('monthly', 200)), float(spec.get('rate', 0.07)), int(spec.get('years', 30))
    comp = spec.get('compounding', 'monthly')
    rows = money_math.invest(monthly, rate, years, float(spec.get('start', 0)), comp)
    bal = [float(spec.get('start', 0))] + [r[2] for r in rows]
    put = [float(spec.get('start', 0))] + [r[1] for r in rows]
    age = spec.get('start_age')
    xl = [(age + i) if age is not None else i for i in range(years + 1)]
    title = spec.get('title') or f'{money(monthly)} a month, invested at {rate:.0%}'
    sub = spec.get('sub') or f'{years} years, compounded {comp}. Example, not a promise.'
    _line_chart(pen, w, h, p, title, sub, xl,
                [{'name': spec.get('name', 'Your money'), 'values': bal, 'color': 'green'},
                 {'name': spec.get('name2', 'You put in'), 'values': put, 'color': 'ink'}])


def chart(pen, w, h, spec, p):
    series = spec.get('series') or [{'name': '', 'values': [0, 1]}]
    _line_chart(pen, w, h, p, spec.get('title', ''), spec.get('sub', ''), spec.get('labels'), series,
                spec.get('prefix', '$'))


def receipt(pen, w, h, spec, p):
    items = [(str(a), float(b)) for a, b in spec.get('items', [])]
    income = spec.get('income')
    rows = ([('PAYCHECK', float(income))] if income is not None else []) + [(a, -b) for a, b in items]
    left = (float(income) if income is not None else 0) - sum(b for _, b in items)
    rh = min(58, (h - 260) / max(1, len(rows)))
    rw = min(w, 640)
    x0 = (w - rw) / 2
    total_h = 120 + rh * len(rows) + 110
    y0 = max(10, (h - total_h) / 2)
    zig = [(x0 + rw * i / 16, y0 + total_h + (12 if i % 2 else 0)) for i in range(16, -1, -1)]
    pen.poly([(x + 10, y + 14) for x, y in [(x0, y0), (x0 + rw, y0)] + zig], (0, 0, 0, 45))
    pen.poly([(x0, y0), (x0 + rw, y0)] + zig, (252, 250, 244))
    pen.text((w / 2, y0 + 55), spec.get('title', 'WHERE IT WENT'), 'type', 44, INK, anchor='mm')
    pen.line([(x0 + 34, y0 + 96), (x0 + rw - 34, y0 + 96)], 2, INK, caps=False)
    shown = int(len(rows) * seg(p, 0.05, 0.75) + 0.999)
    for i, (lab, amt) in enumerate(rows[:shown]):
        y = y0 + 128 + i * rh
        pen.text((x0 + 34, y), lab, 'type', 30, INK, anchor='lm')
        pen.text((x0 + rw - 34, y), ('+' if amt > 0 else '') + money(amt), 'type', 30, GREEN if amt > 0 else RED,
                 anchor='rm')
    if p >= 0.8:
        y = y0 + 110 + rh * len(rows)
        pen.line([(x0 + 34, y), (x0 + rw - 34, y)], 3, INK, caps=False)
        pen.text((x0 + 34, y + 52), spec.get('total_label', 'LEFT OVER'), 'type', 38, INK, anchor='lm')
        income_v = float(income) if income is not None else 0
        good = left > 0 and (income is None or left >= 0.1 * income_v)
        pen.text((x0 + rw - 34, y + 52), money(left), 'display', 60, GREEN if good else RED, anchor='rm')


def phone(pen, w, h, spec, p):
    """Bank notifications that slide in one by one (style "phone" keeps the old phone screen)."""
    if spec.get('style') == 'phone':
        return _phone_screen(pen, w, h, spec, p)
    b1 = float(spec.get('balance', 0))
    b0 = float(spec.get('from', b1))
    b = b0 + (b1 - b0) * ease_in_out(seg(p, 0.0, 0.9))
    items = [(str(a), float(b_)) for a, b_ in (spec.get('items') or [])][:4]
    tw = min(w - 40, 980)
    x0 = (w - tw) / 2
    head_h = 210
    gap = 22
    th = min(150, (h - head_h - gap - 20) / max(1, len(items)) - gap) if items else 0
    total = head_h + (gap + th) * len(items)
    y = (h - total) / 2
    good = b >= b0 and b > 0
    _toast(pen, x0, y, tw, head_h, spec.get('label', 'Checking'), 'Available balance', money(b, '$', 2),
           GREEN if good else RED, 1.0, big=True)
    for i, (lab, amt) in enumerate(items):
        q = ease_in_out(seg(p, 0.12 + i * 0.16, 0.3 + i * 0.16))
        if q <= 0:
            continue
        yy = y + head_h + gap + i * (th + gap)
        off = (1 - q) * (w - x0 + 40)
        _toast(pen, x0 + off, yy, tw, th, lab, 'Card payment', '-' + money(amt), RED, q)


def _toast(pen, x, y, w, h, title, sub, amount, col, q, big=False):
    pen.rect((x + 8, y + 12, x + w + 8, y + h + 12), (0, 0, 0, 45), r=h / 2 if not big else 46)
    pen.rect((x, y, x + w, y + h), (255, 255, 255), (214, 214, 220), 3, r=h / 2 if not big else 46)
    r = h * 0.3
    pen.circle(x + h * 0.5, y + h / 2, r, col)
    pen.text((x + h * 0.5, y + h / 2 + 3), '$', 'display', r * 1.3, (255, 255, 255), anchor='mm')
    tx = x + h * 0.5 + r + 30
    amt_size = fit(pen, amount, 'display', 110 if big else 72, w * 0.45)
    room = w - (tx - x) - pen.text_w(amount, 'display', amt_size) - 60
    pen.text((tx, y + h * 0.36), title, 'bold', fit(pen, title, 'bold', 50 if big else 42, room), INK, anchor='lm')
    pen.text((tx, y + h * 0.7), sub, 'body', fit(pen, sub, 'body', 34 if big else 30, room), MUTED, anchor='lm')
    pen.text((x + w - 40, y + h / 2), amount, 'display', amt_size, col, anchor='rm')


def _phone_screen(pen, w, h, spec, p):
    pw, ph = 380, min(h, 680)
    x0, y0 = (w - pw) / 2, (h - ph) / 2
    pen.rect((x0 + 12, y0 + 16, x0 + pw + 12, y0 + ph + 16), (0, 0, 0, 60), r=52)
    pen.rect((x0, y0, x0 + pw, y0 + ph), INK, r=52)
    pen.rect((x0 + 16, y0 + 18, x0 + pw - 16, y0 + ph - 18), (252, 252, 249), r=38)
    pen.rect((x0 + pw / 2 - 46, y0 + 30, x0 + pw / 2 + 46, y0 + 44), INK, r=7)
    pen.text((x0 + pw / 2, y0 + 100), spec.get('label', 'CHECKING'), 'semi', 28, MUTED, anchor='mm')
    b1 = float(spec.get('balance', 0))
    b0 = float(spec.get('from', b1))
    b = b0 + (b1 - b0) * ease_in_out(seg(p, 0.0, 0.9))
    txt = money(b, '$', 2)
    pen.text((x0 + pw / 2, y0 + 195), txt, 'display', fit(pen, txt, 'display', 104, pw - 60),
             RED if b <= b0 and b < 100 else (GREEN if b > 0 else RED), anchor='mm')
    pen.text((x0 + pw / 2, y0 + 270), 'Available balance', 'body', 26, MUTED, anchor='mm')
    for i, (lab, amt) in enumerate(spec.get('items', [])[:5]):
        y = y0 + 340 + i * 62
        pen.line([(x0 + 40, y - 30), (x0 + pw - 40, y - 30)], 1.5, LINE, caps=False)
        pen.text((x0 + 42, y), str(lab), 'body', 28, INK, anchor='lm')
        pen.text((x0 + pw - 42, y), '-' + money(float(amt)), 'semi', 28, RED, anchor='rm')


def compare(pen, w, h, spec, p):
    L, Rr = spec.get('left', {}), spec.get('right', {})
    prefix, suffix = spec.get('prefix', '$'), spec.get('suffix', '')
    vals = [float(L.get('value', 0)), float(Rr.get('value', 0))]
    vmax = max(vals) or 1
    if spec.get('title'):
        pen.text((w / 2, 40), spec['title'], 'bold', fit(pen, spec['title'], 'bold', 50, w - 40), INK, anchor='mt')
    base, top = h - 120, 250 if spec.get('title') else 150
    bw = min(220, w / 4)
    k = ease_in_out(seg(p, 0.1, 0.8))
    for j, (side, val) in enumerate(zip((L, Rr), vals)):
        cx = w * (0.3 if j == 0 else 0.7)
        col = COLORS.get(side.get('color', 'green' if val == vmax else 'red'), GREEN)
        bh = (base - top) * val / vmax * k
        pen.rect((cx - bw / 2, base - bh, cx + bw / 2, base), col, INK, 4, r=14)
        pen.text((cx, base + 22), side.get('label', ''), 'semi', fit(pen, side.get('label', ''), 'semi', 38, w * 0.42),
                 INK, anchor='mt')
        if k > 0.6:
            pen.text((cx, base - bh - 16), money(val * k, prefix) + suffix, 'display', 64, col, anchor='mb')
    pen.line([(40, base), (w - 40, base)], 4, INK, caps=False)


def checklist(pen, w, h, spec, p):
    """A yellow sticky note with a handwritten list, ticked or crossed line by line (style "card": the old list)."""
    if spec.get('style') == 'card':
        return _checklist_plain(pen, w, h, spec, p)
    items = spec.get('items', [])
    title = spec.get('title', '')
    nw = min(w - 80, 820)
    rh = 96 if len(items) <= 4 else max(64, 96 - (len(items) - 4) * 10)
    nh = min(h - 70, (150 if title else 50) + rh * len(items) + 50)
    x0, y0 = (w - nw) / 2, (h - nh) / 2 + 10
    shape = [(x0, y0), (x0 + nw, y0), (x0 + nw, y0 + nh), (x0, y0 + nh)]

    def draw_note(lay):
        sh = lay.layer()
        sh.poly([(x + 12, y + 16) for x, y in shape], (0, 0, 0, 55))
        lay.paste(sh, blur=12)
        lay.poly(shape, (255, 232, 120))
        lay.poly([(x0 + nw - 80, y0 + nh), (x0 + nw, y0 + nh - 80), (x0 + nw, y0 + nh)], (236, 205, 90))
        if title:
            size = fit(lay, title, 'hand', 76, nw - 100)
            lay.text((x0 + 50, y0 + 74), title, 'hand', size, INK, anchor='lm')
            lay.line([(x0 + 50, y0 + 122), (x0 + 50 + min(nw - 100, lay.text_w(title, 'hand', size)), y0 + 119)], 4, RED)
        tape = lay.layer()
        tape.rect((w / 2 - 120, y0 - 26, w / 2 + 120, y0 + 30), (190, 220, 255, 170))
        lay.paste(tape, rotate=-4)

    lay = _cached_layer(pen, ('note', title, len(items), nw, nh), draw_note)
    y = y0 + 40 + (130 if title else 0)
    shown = len(items) * seg(p, 0.0, 0.8)
    for i, it in enumerate(items):
        q = clamp(shown - i)
        if q <= 0:
            break
        good = not str(it).startswith('-')
        text = str(it).lstrip('+- ')
        yy = y + i * rh + rh / 2
        mark = clamp(q * 1.6)
        if good:
            _part_line(lay, [(x0 + 54, yy), (x0 + 72, yy + 20), (x0 + 104, yy - 22)], mark, 8, GREEN)
        else:
            _part_line(lay, [(x0 + 54, yy - 18), (x0 + 90, yy + 18)], clamp(mark * 2), 8, RED)
            _part_line(lay, [(x0 + 90, yy - 18), (x0 + 54, yy + 18)], clamp(mark * 2 - 1), 8, RED)
        size = fit(lay, text, 'hand', 60, nw - 170)
        if q >= 1:
            lay.text((x0 + 120, yy + 2), text, 'hand', size, INK, anchor='lm')
        else:                                                # the words are written left to right
            tl = lay.layer()
            tl.text((x0 + 120, yy + 2), text, 'hand', size, INK, anchor='lm')
            cut = int((x0 + 120 + lay.text_w(text, 'hand', size) * q) * tl.S)
            tl.img.paste((0, 0, 0, 0), (cut, 0, tl.img.width, tl.img.height))
            lay.paste(tl)
    pen.paste(lay, rotate=2)


def _part_line(pen, pts, f, width, col):
    """Draws the first fraction f of a polyline (a pen stroke being made)."""
    if f <= 0:
        return
    segs = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    left = sum(segs) * f
    out = [pts[0]]
    for (a, b), L in zip(zip(pts, pts[1:]), segs):
        if left >= L:
            out.append(b)
            left -= L
        else:
            out.append((a[0] + (b[0] - a[0]) * left / L, a[1] + (b[1] - a[1]) * left / L))
            break
    pen.line(out, width, col)


def _checklist_plain(pen, w, h, spec, p):
    items = spec.get('items', [])
    title = spec.get('title', '')
    y = 40
    if title:
        pen.text((40, y), title, 'bold', fit(pen, title, 'bold', 54, w - 80), INK)
        y += 100
    rh = min(92, (h - y - 20) / max(1, len(items)))
    shown = int(len(items) * seg(p, 0.0, 0.8) + 0.999)
    for i, it in enumerate(items[:shown]):
        good = not str(it).startswith('-')
        text = str(it).lstrip('+- ')
        yy = y + i * rh + rh / 2
        col = GREEN if good else RED
        pen.circle(64, yy, 26, col)
        if good:
            pen.line([(52, yy), (61, yy + 10), (78, yy - 10)], 6, (255, 255, 255))
        else:
            pen.line([(54, yy - 10), (74, yy + 10)], 6, (255, 255, 255))
            pen.line([(74, yy - 10), (54, yy + 10)], 6, (255, 255, 255))
        pen.text((110, yy), text, 'semi', fit(pen, text, 'semi', 46, w - 150), INK, anchor='lm')


def subscribe(pen, w, h, spec, p):
    """End card: a Subscribe button that a cursor clicks (it turns into SUBSCRIBED), the bell rings, and two
    dashed "Watch next" frames mark where YouTube end-screen videos go."""
    title = spec.get('text', 'NEW VIDEOS EVERY WED & SAT')
    pen.text((w / 2, 60), title, 'display', fit(pen, title, 'display', 64, w - 60), INK, anchor='mm')
    clicked = p >= 0.5
    bx, by, bw, bh = w * 0.36, 230, 470, 120
    squish = 1 - 0.08 * math.sin(math.pi * seg(p, 0.48, 0.56))
    hw, hh = bw / 2 * squish, bh / 2 * squish
    pen.rect((bx - hw + 8, by - hh + 10, bx + hw + 8, by + hh + 10), (0, 0, 0, 50), r=hh)
    if clicked:
        pen.rect((bx - hw, by - hh, bx + hw, by + hh), (229, 229, 229), INK, 4, r=hh)
        pen.text((bx + 18, by + 2), 'SUBSCRIBED', 'display', 52, (90, 90, 90), anchor='mm')
        pen.line([(bx - hw + 36, by), (bx - hw + 52, by + 16), (bx - hw + 80, by - 16)], 8, GREEN)
    else:
        pen.rect((bx - hw, by - hh, bx + hw, by + hh), (220, 30, 40), INK, 4, r=hh)
        pen.text((bx, by + 2), 'SUBSCRIBE', 'display', 60, (255, 255, 255), anchor='mm')
    # the bell, ringing after the click
    cx, cy = bx + bw / 2 + 110, by
    ring = math.sin(seg(p, 0.55, 0.9) * math.pi * 6) * 18 * (1 - seg(p, 0.55, 0.9)) if p > 0.55 else 0
    bell = pen.layer()
    bell.circle(cx, cy, 62, (255, 255, 255), INK, 4)
    bell.poly([(cx - 30, cy + 22), (cx - 24, cy - 14), (cx - 12, cy - 30), (cx + 12, cy - 30), (cx + 24, cy - 14),
               (cx + 30, cy + 22)], GOLD if clicked else (200, 200, 200), INK, 4)
    bell.circle(cx, cy + 30, 8, INK)
    bell.circle(cx, cy - 34, 6, INK)
    pen.paste(bell, rotate=ring, center=(cx, cy - 34))
    # the cursor glides in and clicks
    if p < 0.75:
        q = ease_in_out(seg(p, 0.15, 0.46))
        mx = w * 0.95 + (bx + 60 - w * 0.95) * q
        my = h * 0.95 + (by + 20 - h * 0.95) * q
        s = 1.0 if not (0.46 <= p < 0.54) else 0.85
        arrow = [(0, 0), (0, 64 * s), (16 * s, 50 * s), (28 * s, 76 * s), (40 * s, 70 * s), (28 * s, 45 * s), (48 * s, 45 * s)]
        pen.poly([(mx + x, my + y) for x, y in arrow], (255, 255, 255), INK, 4)
    # where the YouTube end-screen videos will sit
    fw, fh = 500, 281
    for i in range(2):
        fx = w / 2 - fw - 20 if i == 0 else w / 2 + 20
        fy = h - fh - 40
        for k in range(0, int(fw), 30):
            pen.line([(fx + k, fy), (fx + min(fw, k + 16), fy)], 4, MUTED, caps=False)
            pen.line([(fx + k, fy + fh), (fx + min(fw, k + 16), fy + fh)], 4, MUTED, caps=False)
        for k in range(0, int(fh), 30):
            pen.line([(fx, fy + k), (fx, fy + min(fh, k + 16))], 4, MUTED, caps=False)
            pen.line([(fx + fw, fy + k), (fx + fw, fy + min(fh, k + 16))], 4, MUTED, caps=False)
        pen.text((fx + fw / 2, fy + fh / 2), 'WATCH NEXT', 'bold', 40, MUTED, anchor='mm')


DRAW = {'money_card': money_card, 'big_text': big_text, 'invest_chart': invest_chart, 'chart': chart,
        'receipt': receipt, 'phone': phone, 'compare': compare, 'list': checklist,
        'subscribe': subscribe}


def quantize(spec, p):
    """The progress values an element is actually redrawn at: still cards are drawn once, moving parts get
    just enough steps to look smooth. Frames between steps reuse the cached image."""
    t = spec.get('type')
    if t == 'money_card':
        if 'to' in spec:
            return round(p * 90) / 90
        if card_style(spec) == 'tag':
            return round(p * 50) / 50 if p < 0.6 else 1.0       # swings, then hangs still
        return 1.0
    if t == 'big_text':
        return 1.0
    if t == 'subscribe':
        return round(p * 60) / 60
    if t == 'list':
        return round(p * 30) / 30
    if t == 'phone':
        return round(p * 60) / 60
    return round(p * 90) / 90


def render(spec, w, h, p, S=2):
    """Returns an RGBA image (w x h) of the element at progress p, or None for types drawn elsewhere."""
    fn = DRAW.get(spec.get('type'))
    if not fn:
        return None
    pen = Pen(int(w), int(h), S)
    fn(pen, w, h, spec, p)
    return pen.done()
