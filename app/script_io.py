"""Load, normalise and check Money Studio scripts (JSON). Messages to the user are in Vietnamese."""
import json
import re

BGS = ['grid', 'room', 'desk', 'notebook', 'city', 'plain']
SHOWS = ['money_card', 'big_text', 'invest_chart', 'chart', 'receipt', 'phone', 'compare', 'list', 'coin_drop',
         'sketch']
SKETCH_KINDS = ['line', 'bars', 'pie', 'flow']
WHO = ['ben', 'piggy']
POSES = {'ben': ['idle', 'wave', 'point', 'hold_head', 'cross_arms', 'phone', 'read', 'count_money', 'shrug',
                 'think', 'celebrate', 'thumbs_up', 'facepalm', 'explain', 'sad',
                 'sit_desk', 'empty_pockets', 'credit_card', 'shopping_bags', 'coffee', 'calculator', 'beg',
                 'throw_money', 'hug_piggy', 'present'],
         'piggy': ['idle']}
MOODS = ['smile', 'shock', 'sad', 'worried', 'angry', 'smug', 'money_eyes', 'tired', 'cry']
PURPOSES = ['hook', 'promise', 'setup', 'open_loop', 'beat', 'rehook', 'payoff', 'action', 'outro']
TRANSITIONS = ['cut', 'fade', 'slide']
MUSIC = ['light', 'thoughtful', 'none']
SFX = ['pop', 'coin', 'ding', 'whoosh', 'tick', 'thud', 'cash', 'page', 'scribble']
SUB_LANGS = {'en': 'Tiếng Anh', 'vi': 'Tiếng Việt', 'none': 'Không phụ đề'}


def library():
    return {'backgrounds': BGS, 'show_types': SHOWS, 'characters': WHO, 'poses': POSES, 'moods': MOODS,
            'purposes': PURPOSES, 'transitions': TRANSITIONS, 'music': MUSIC, 'sfx': SFX}


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return normalise(json.load(f))


def normalise(s):
    s = dict(s)
    s.setdefault('title', 'Untitled')
    s.setdefault('mascot', 'ben')
    nar = dict(s.get('narrator') or {})
    nar.setdefault('voice', '')
    nar.setdefault('speed', 1.0)
    s['narrator'] = nar
    s.setdefault('music', 'light')
    s.setdefault('youtube', {})
    s.setdefault('thumbnail', {})
    scenes = []
    prev_bg = 'grid'
    for i, sc in enumerate(s.get('scenes') or []):
        sc = dict(sc)
        sc['index'] = i
        sc.setdefault('purpose', 'beat')
        sc['bg'] = sc.get('bg') or prev_bg
        prev_bg = sc['bg']
        if 'chars' not in sc:
            sc['chars'] = [{'who': s['mascot'] if s['mascot'] in WHO else 'ben'}]
        chars = []
        for c in sc['chars'] or []:
            c = dict(c) if isinstance(c, dict) else {'who': str(c)}
            c.setdefault('who', 'ben')
            c.setdefault('pose', 'idle')
            c.setdefault('mood', 'smile')
            chars.append(c)
        sc['chars'] = chars
        lines = []
        for ln in sc.get('lines') or []:
            ln = dict(ln) if isinstance(ln, dict) else {'text': str(ln)}
            ln['text'] = (ln.get('text') or '').strip()
            ln['vi'] = (ln.get('vi') or '').strip()
            ln.setdefault('pause_after', 0.25)
            ln.setdefault('speaker', 'narrator')
            if ln['text']:
                lines.append(ln)
        sc['lines'] = lines
        sc.setdefault('transition', 'cut')
        sc['sfx'] = list(sc.get('sfx') or [])
        scenes.append(sc)
    s['scenes'] = scenes
    return s


def missing_vi(s):
    return sum(1 for sc in s['scenes'] for ln in sc['lines'] if not ln.get('vi'))


def check(s):
    """Returns a list of (level, message). level: 'LỖI' (blocks export) or 'CHÚ Ý'."""
    out = []
    if not s['scenes']:
        return [('LỖI', 'Kịch bản không có cảnh nào.')]
    if s['scenes'][0]['purpose'] != 'hook':
        out.append(('CHÚ Ý', 'Cảnh 1 nên là "hook": câu đầu tiên phải kéo người xem ngay giây đầu.'))
    for sc in s['scenes']:
        n = sc['index'] + 1
        if sc['bg'] not in BGS:
            out.append(('LỖI', f'Cảnh {n}: nền "{sc["bg"]}" không có. Dùng: {", ".join(BGS)}'))
        show = sc.get('show')
        if show and show.get('type') == 'sketch' and show.get('kind', 'line') not in SKETCH_KINDS:
            out.append(('LỖI', f'Cảnh {n}: sketch kind "{show.get("kind")}" không có. Dùng: {", ".join(SKETCH_KINDS)}'))
        if show and show.get('type') not in SHOWS:
            out.append(('LỖI', f'Cảnh {n}: show.type "{show.get("type")}" không có. Dùng: {", ".join(SHOWS)}'))
        for c in sc['chars']:
            if c['who'] not in WHO:
                out.append(('LỖI', f'Cảnh {n}: nhân vật "{c["who"]}" không có (ben, piggy).'))
            elif c['pose'] not in POSES[c['who']]:
                out.append(('CHÚ Ý', f'Cảnh {n}: {c["who"]} chưa có dáng "{c["pose"]}", tool dùng dáng mặc định.'))
            if c['mood'] not in MOODS:
                out.append(('CHÚ Ý', f'Cảnh {n}: cảm xúc "{c["mood"]}" chưa có, dùng "smile".'))
        if not sc['lines']:
            out.append(('CHÚ Ý', f'Cảnh {n}: không có lời đọc (cảnh sẽ dài 2 giây).'))
        words = sum(len(ln['text'].split()) for ln in sc['lines'])
        if words > 26:
            out.append(('CHÚ Ý', f'Cảnh {n}: {words} từ (khoảng {words / 2.6:.0f} giây). Nên tách cảnh, mỗi cảnh 3-7 giây.'))
        for ln in sc['lines']:
            if len(ln['text'].split()) > 22:
                out.append(('CHÚ Ý', f'Cảnh {n}: câu dài hơn 22 từ, nên cắt ngắn: "{ln["text"][:50]}..."'))
            if re.search(r'\d', ln['text']):
                out.append(('CHÚ Ý', f'Cảnh {n}: lời đọc có chữ số, nên viết bằng chữ để giọng đọc chuẩn: "{ln["text"][:50]}"'))
        for e in sc['sfx']:
            if e.get('name') not in SFX:
                out.append(('CHÚ Ý', f'Cảnh {n}: hiệu ứng "{e.get("name")}" không có. Dùng: {", ".join(SFX)}'))
    if s['music'] not in MUSIC:
        out.append(('CHÚ Ý', f'Nhạc "{s["music"]}" không có, dùng "light".'))
    mv = missing_vi(s)
    if mv:
        out.append(('CHÚ Ý', f'{mv} câu chưa có bản dịch tiếng Việt ("vi"). Phụ đề tiếng Việt sẽ dùng tiếng Anh cho các câu đó '
                              '(hoặc bấm "Dịch phụ đề tiếng Việt" ở tab 2 nếu có API key).'))
    desc = (s.get('youtube') or {}).get('description', '')
    if 'not financial advice' not in desc.lower():
        out.append(('CHÚ Ý', 'Mô tả YouTube chưa có dòng "not financial advice" (tool sẽ tự thêm vào youtube.txt).'))
    chapters = [sc for sc in s['scenes'] if sc.get('chapter')]
    if 0 < len(chapters) < 3:
        out.append(('CHÚ Ý', 'YouTube cần ít nhất 3 chương; đang có %d.' % len(chapters)))
    return out
