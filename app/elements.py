"""On-screen money elements. Each draws into its own box and depends only on `p` (0..1 progress through
its animation), so frames can be cached. Every number shown is computed here, never typed by hand.
"""
import math
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
    cw, ch = min(w, 760), min(h, 420)
    x0, y0 = (w - cw) / 2, (h - ch) / 2
    _card(pen, x0, y0, x0 + cw, y0 + ch)
    if label:
        pen.text((w / 2, y0 + 78), label.upper(), 'bold', fit(pen, label.upper(), 'bold', 44, cw - 80), MUTED,
                 anchor='mm')
    txt = money(v, spec.get('prefix', '$'), int(spec.get('decimals', 0)))
    pen.text((w / 2, y0 + ch * 0.58), txt, 'display', fit(pen, txt, 'display', 190, cw - 80), col, anchor='mm')
    if spec.get('note'):
        pen.text((w / 2, y0 + ch - 50), spec['note'], 'body', fit(pen, spec['note'], 'body', 34, cw - 80), MUTED,
                 anchor='mm')


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


DRAW = {'money_card': money_card, 'big_text': big_text, 'invest_chart': invest_chart, 'chart': chart,
        'receipt': receipt, 'phone': phone, 'compare': compare, 'list': checklist}


def render(spec, w, h, p, S=2):
    """Returns an RGBA image (w x h) of the element at progress p, or None for types drawn elsewhere."""
    fn = DRAW.get(spec.get('type'))
    if not fn:
        return None
    pen = Pen(int(w), int(h), S)
    fn(pen, w, h, spec, p)
    return pen.done()
