"""Three thumbnails (1280x720) for YouTube Test & Compare.

Layouts:
  face_number : big mascot reaction on the left, one huge number on the right, 2-4 words on top
  object      : a money object (phone balance or receipt) with the mascot peeking
  split       : before -> after, green number on the left, red on the right, mascot in the middle
Spec (script.thumbnail.variants[i]): layout, text (wrap a word in *stars* for the accent colour),
number, left, right, who (ben|piggy), pose (any Ben pose), mood (smile|shock|sad|worried|angry|smug),
accent (red|green|gold).
"""
import math
from PIL import Image
from engine.flatkit import Pen
from engine import charkit
import elements as EL

TW, TH = 1280, 720
INK, CREAM = (29, 33, 45), (246, 241, 230)
ACC = {'red': (214, 69, 69), 'green': (46, 139, 87), 'gold': (230, 160, 20)}


def _bg(p, accent):
    p.vgrad((0, 0, TW, TH), '#FBF6EA', '#EADFC8')
    lay = p.layer()
    cx, cy = TW * 0.3, TH * 0.45
    for i in range(18):
        a0, a1 = math.radians(i * 20), math.radians(i * 20 + 10)
        lay.poly([(cx, cy), (cx + 1600 * math.cos(a0), cy + 1600 * math.sin(a0)),
                  (cx + 1600 * math.cos(a1), cy + 1600 * math.sin(a1))], (255, 214, 120, 55))
    p.paste(lay)


def _mascot(who, mood, height, pose=None):
    if who == 'piggy':
        im = charkit.piggy(mood='shock' if mood in ('shock', 'sad', 'worried', 'angry') else 'smile', scale=2)
    else:
        pose = pose or ('hold_head' if mood in ('shock', 'worried') else 'point')
        im = charkit.ben(pose, mood, scale=2)
    im = im.crop(im.getbbox())
    k = height / im.height
    im = im.resize((int(im.width * k), int(height)), Image.LANCZOS)
    # white sticker rim for phone-size contrast
    from PIL import ImageFilter
    a = im.getchannel('A').filter(ImageFilter.MaxFilter(13))
    rim = Image.new('RGBA', im.size, (255, 255, 255, 255))
    rim.putalpha(a)
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    out.alpha_composite(rim)
    out.alpha_composite(im)
    return out


def _headline(p, text, accent, x, y, max_w, size=96, anchor='la'):
    parts = text.upper().split('*')
    total = sum(p.text_w(s, 'display', size) for s in parts)
    while total > max_w and size > 40:
        size -= 4
        total = sum(p.text_w(s, 'display', size) for s in parts)
    if anchor == 'ma':
        x -= total / 2
    hi = False
    for s in parts:
        if s:
            p.text((x, y), s, 'display', size, ACC.get(accent, ACC['red']) if hi else INK)
            x += p.text_w(s, 'display', size)
        hi = not hi


def render(spec, script):
    accent = spec.get('accent', 'red')
    who = spec.get('who') or (script.get('mascot') if script.get('mascot') in ('ben', 'piggy') else 'ben')
    mood = spec.get('mood', 'shock')
    layout = spec.get('layout', 'face_number')
    p = Pen(TW, TH)
    _bg(p, accent)
    text = spec.get('text', '')
    if layout == 'split':
        tint = p.layer()                       # translucent fills must be blended, not written
        tint.rect((0, 0, TW / 2, TH), (46, 139, 87, 46))
        tint.rect((TW / 2, 0, TW, TH), (214, 69, 69, 46))
        p.paste(tint)
        p.text((TW * 0.25, TH * 0.52), spec.get('left', ''), 'display', 150, ACC['green'], anchor='mm')
        p.text((TW * 0.75, TH * 0.52), spec.get('right', ''), 'display', 150, ACC['red'], anchor='mm')
        p.poly([(TW / 2 - 50, TH * 0.47), (TW / 2 + 40, TH * 0.52), (TW / 2 - 50, TH * 0.57)], INK)
        if text:
            _headline(p, text, accent, TW / 2, 34, TW - 80, 92, anchor='ma')
        img = p.done()
        m = _mascot(who, mood, TH * 0.42, spec.get('pose'))
        img.alpha_composite(m, (int(TW / 2 - m.width / 2), TH - m.height + 10))
        return img
    if layout == 'object':
        el = EL.render({'type': 'phone', 'label': 'CHECKING', 'balance': float(spec.get('balance', 0)),
                        'items': spec.get('items', [['Rent', 1450], ['Car loan', 489], ['Takeout', 312]])},
                       460, 640, 1.0)
        if text:
            _headline(p, text, accent, 40, 40, TW * 0.52, 104)
        img = p.done()
        img.alpha_composite(el.rotate(-6, resample=Image.BICUBIC, expand=True), (int(TW * 0.6), 20))
        m = _mascot(who, mood, TH * 0.72, spec.get('pose'))
        img.alpha_composite(m, (int(TW * 0.2), TH - m.height + 20))
        return img
    # face_number
    if text:
        _headline(p, text, accent, 40, 34, TW * 0.9, 100)
    num = spec.get('number', '')
    if num:
        size = 220
        while p.text_w(num, 'display', size) > TW * 0.5 and size > 80:
            size -= 8
        p.text((TW * 0.73, TH * 0.6), num, 'display', size, ACC.get(accent, ACC['red']), anchor='mm', stroke=6,
               stroke_fill=(255, 255, 255))
    img = p.done()
    m = _mascot(who, mood, TH * 0.76, spec.get('pose'))
    img.alpha_composite(m, (int(TW * 0.25 - m.width / 2), TH - m.height + 24))
    return img


def render_all(script):
    variants = (script.get('thumbnail') or {}).get('variants') or []
    if not variants:
        variants = [{'layout': 'face_number', 'text': script.get('title', '')[:24], 'number': '$0'}]
    while len(variants) < 3:
        variants.append(variants[-1])
    return [render(v, script) for v in variants[:3]]
